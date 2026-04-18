use std::collections::HashSet;
use std::io;

use dimos_native_module::{LcmTransport, NativeModule};
use lcm_msgs::sensor_msgs::{PointCloud2, PointField};
use lcm_msgs::std_msgs::{Header, Time};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct VoxelMapperConfig {
    voxel_size: f32,
    carve_columns: bool,
    output_frame_id: String,
}

fn extract_xyz(cloud: &PointCloud2) -> Vec<[f32; 3]> {
    let mut x_off = 0usize;
    let mut y_off = 4usize;
    let mut z_off = 8usize;

    for f in &cloud.fields {
        match f.name.as_str() {
            "x" => x_off = f.offset as usize,
            "y" => y_off = f.offset as usize,
            "z" => z_off = f.offset as usize,
            _ => {}
        }
    }

    let step = cloud.point_step as usize;
    let num = (cloud.width * cloud.height) as usize;
    let data = &cloud.data;
    let mut points = Vec::with_capacity(num);

    for i in 0..num {
        let base = i * step;
        if base + z_off + 4 > data.len() {
            break;
        }
        let read_f32 = |off: usize| -> f32 {
            f32::from_le_bytes(data[base + off..base + off + 4].try_into().unwrap())
        };
        let x = read_f32(x_off);
        let y = read_f32(y_off);
        let z = read_f32(z_off);
        if x.is_finite() && y.is_finite() && z.is_finite() {
            points.push([x, y, z]);
        }
    }
    points
}

fn add_frame(cloud: &PointCloud2, voxels: &mut HashSet<[i32; 3]>, cfg: &VoxelMapperConfig) {
    let points = extract_xyz(cloud);
    let inv = 1.0 / cfg.voxel_size;

    let new_keys: Vec<[i32; 3]> = points
        .iter()
        .map(|p| [(p[0] * inv).floor() as i32, (p[1] * inv).floor() as i32, (p[2] * inv).floor() as i32])
        .collect();

    if cfg.carve_columns {
        let xy_set: HashSet<[i32; 2]> = new_keys.iter().map(|k| [k[0], k[1]]).collect();
        voxels.retain(|k| !xy_set.contains(&[k[0], k[1]]));
    }

    for key in new_keys {
        voxels.insert(key);
    }
}

fn build_output(voxels: &HashSet<[i32; 3]>, cfg: &VoxelMapperConfig, ts: f64) -> PointCloud2 {
    let half = cfg.voxel_size * 0.5;
    let n = voxels.len();
    let mut data = Vec::with_capacity(n * 12);

    for [vx, vy, vz] in voxels {
        let x = *vx as f32 * cfg.voxel_size + half;
        let y = *vy as f32 * cfg.voxel_size + half;
        let z = *vz as f32 * cfg.voxel_size + half;
        data.extend_from_slice(&x.to_le_bytes());
        data.extend_from_slice(&y.to_le_bytes());
        data.extend_from_slice(&z.to_le_bytes());
    }

    let sec = ts as i32;
    let nsec = ((ts - sec as f64) * 1e9) as i32;

    PointCloud2 {
        header: Header {
            seq: 0,
            stamp: Time { sec, nsec },
            frame_id: cfg.output_frame_id.clone(),
        },
        height: 1,
        width: n as i32,
        fields: vec![
            PointField { name: "x".into(), offset: 0,  datatype: 7, count: 1 },
            PointField { name: "y".into(), offset: 4,  datatype: 7, count: 1 },
            PointField { name: "z".into(), offset: 8,  datatype: 7, count: 1 },
        ],
        is_bigendian: false,
        point_step: 12,
        row_step: (n as i32) * 12,
        data,
        is_dense: true,
    }
}

#[tokio::main]
async fn main() -> io::Result<()> {
    let transport = LcmTransport::new().await.expect("failed to create LCM transport");
    let (mut module, config) = NativeModule::from_stdin::<VoxelMapperConfig>(transport)
        .await
        .expect("failed to read config from stdin");

    let mut lidar = module.input("lidar", PointCloud2::decode);
    let global_map = module.output("global_map", PointCloud2::encode);
    let _handle = module.spawn();

    eprintln!(
        "voxelmapper ready: voxel_size={} carve_columns={} output_frame_id={}",
        config.voxel_size, config.carve_columns, config.output_frame_id
    );

    let mut voxels: HashSet<[i32; 3]> = HashSet::new();
    let mut latest_ts: f64;

    loop {
        match lidar.recv().await {
            Some(cloud) => {
                latest_ts = cloud.header.stamp.sec as f64 + cloud.header.stamp.nsec as f64 * 1e-9;
                add_frame(&cloud, &mut voxels, &config);
                let out = build_output(&voxels, &config, latest_ts);
                global_map.publish(&out).await.ok();
            }
            None => break,
        }
    }

    Ok(())
}
