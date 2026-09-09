# Wheatstone

Turn two Spirit rover images into a measured patch of Mars, then move a camera through it.

[Watch the 44-second flythrough](demo/wheatstone.mp4) · [Textured mesh](output/terrain.obj) · [Results](output/metrics.json)

![A camera move through the reconstructed Martian surface](demo/poster.png)

Real stereo images provide the texture and depth. The pipeline reads each image's camera calibration, finds corresponding pixels, triangulates a surface in metres, and leaves unsupported regions empty. No generated terrain, depth model or downloaded mesh is used.

## Run

Python 3.12, FFmpeg with ffprobe, and DejaVu Sans fonts are required. The renderer uses the Debian/Ubuntu `fonts-dejavu-core` paths in `/usr/share/fonts/truetype/dejavu/`. The included results were produced on Linux with a CPU.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_data.py
python scripts/reconstruct.py
python scripts/render.py
python scripts/verify.py
```

Reconstruction writes rectified images, a masked disparity view, a textured OBJ with its MTL and PNG, a rover-frame PLY point cloud, and numerical arrays. Keep `terrain.obj`, `terrain.mtl` and `left.png` together when importing the mesh. The OBJ uses rectified camera coordinates: x right, y down, z forward, in metres. The PLY contains points in the source label's rover frame; it has no faces. The 1080p video is rendered directly from the saved textured triangles.

## What was measured

The pair was acquired by **Spirit's left and right Navcams on sol 767, March 1, 2006**, at approximately 05:33:25 UTC. Both are 1024 × 1024 monochrome EDR images, with embedded CAHVOR camera models. The left product is `2N194463440EFFAPA0P0685L0M1`; the right product differs by `R0M1`.

| Quantity | Result |
|---|---:|
| Camera baseline | 0.200345 m |
| Accepted stereo pixels | 602,875 |
| Mesh vertices / triangles | 66,459 / 126,521 |
| Forward depth, 5th / 50th / 95th percentile | 2.25 / 4.05 / 18.62 m |
| Median / 95th percentile left–right cycle error | 0.0625 / 0.1563 px |
| Median vertical feature residual after registration | 0.1687 px |
| Median depth sensitivity to one disparity pixel | 0.0712 m |

The last number is a geometric sensitivity, **not an estimated accuracy or confidence interval**. Depth here means distance along the rectified camera's forward axis, not Euclidean range.

The cameras are rectified through the published CAHVOR distortion model into a shared 1,150-pixel focal length. A 0.631-pixel vertical translation estimated from SIFT feature matches refines registration. OpenCV SGBM estimates disparity independently in both directions; only pixels with less than one pixel of cycle error, valid source coverage and depths between 0.8 and 30 m survive. Every third pixel supplies a mesh vertex, and triangles spanning excessive depth jumps are removed. The texture uses a common 0.5–99.5 percentile brightness stretch of the two source images.

`verify.py` checks source hashes and camera-frame compatibility, rectification against source pixels, the source-derived baseline and basis, independently recomputed right-to-left matching, depth/metric consistency, triangle support and discontinuities, both export formats, and a complete decode of the required video. These checks establish computational consistency; they do not supply independent ground-truth terrain.

## Scope and sources

This is a small surface reconstruction from one stereo pair, not a complete terrain model. Textureless areas, shadows, occlusions, compression and calibration errors can produce missing or incorrect matches. Cycle consistency can accept mutually wrong matches. The subpixel registration is empirical; its cause is not established by this experiment. No bundle adjustment, additional viewpoints or independent range measurements validate absolute accuracy. The flythrough moves only modestly within the observed patch; black gaps are intentionally retained.

The pair was selected from the PDS archive for this project rather than using a packaged stereo tutorial. **We cannot prove that these public images have never been used elsewhere.**

Original observations: [left PDS product](https://planetarydata.jpl.nasa.gov/img/data/mer/mer2no_0xxx/data/sol0767/edr/2n194463440effapa0p0685l0m1.img), [right PDS product](https://planetarydata.jpl.nasa.gov/img/data/mer/mer2no_0xxx/data/sol0767/edr/2n194463440effapa0p0685r0m1.img). Exact SHA-256 digests are pinned in [data/provenance.json](data/provenance.json); downloads are checked before use. Camera model coefficients remain embedded in the original labels. See the [PDS MER archive documentation](https://pds-imaging.jpl.nasa.gov/portal/mer_mission.html).

Imagery: Courtesy NASA/JPL-Caltech. Original code is MIT-licensed; source imagery and derived textures retain their [data notices](data/NOTICE.md). No NASA, JPL or Caltech endorsement is implied.
