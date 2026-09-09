# Stereo reconstruction

## Inputs

Spirit Navcam EDR stereo pair, sol 767, 2006-03-01T05:33:25.179. Each image is 1024 × 1024 pixels, monochrome, with an embedded CAHVOR model. [Product identifiers and checksums](../data/provenance.json).

## Processing

CAHVOR rectification uses a shared 1,150 px focal length. SIFT matches supply a 0.631 px vertical registration correction. OpenCV SGBM runs in both directions. Acceptance requires cycle error below 1 px, valid source coverage and forward depth between 0.8 and 30 m. Every third pixel supplies a vertex; triangles spanning excessive depth discontinuities are removed. A shared 0.5–99.5 percentile brightness stretch supplies the texture.

| Measurement | Value |
|---|---:|
| Baseline | 0.200345 m |
| Accepted pixels | 602,875 |
| Vertices / triangles | 66,459 / 126,521 |
| Forward depth, 5th / 50th / 95th percentile | 2.25 / 4.05 / 18.62 m |
| Cycle error, median / 95th percentile | 0.0625 / 0.1563 px |
| Vertical registration residual, median | 0.1687 px |
| Depth sensitivity to 1 disparity pixel, median | 0.0712 m |

Forward depth is axial distance. Disparity sensitivity is not an accuracy estimate or confidence interval.

## Validation

`verify.py` checks hashes, camera frames, rectification, baseline, both matching directions, depth, triangle support, export coordinates and full video decoding. These checks establish computational consistency. Absolute accuracy lacks independent range measurements, bundle adjustment or additional views.

Textureless areas, shadows, occlusions, compression and calibration errors can cause missing or incorrect matches. Cycle consistency can accept mutually incorrect matches. The cause of the empirical registration correction is undetermined. Unsupported geometry remains empty. Prior use of these public images is unknown.

## Outputs

The OBJ contains textured triangles in rectified camera coordinates: x right, y down, z forward, in metres. Keep `terrain.obj`, `terrain.mtl` and `left.png` together. The PLY contains rover-frame points without faces. `terrain.npz` retains arrays; `metrics.json` records measurements. The video renders these saved triangles with a translated virtual camera.
