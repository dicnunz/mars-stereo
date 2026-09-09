"""Check source geometry, saved stereo/depth/exports, and the required full movie."""
import json
import re
import subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from fetch_data import main as check_hashes
from reconstruct import read_pds, project

ROOT = Path(__file__).resolve().parents[1]


def close(actual, expected, atol=1e-10):
    np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=atol)


def main():
    check_hashes()
    out = ROOT / 'output'
    m = json.loads((out / 'metrics.json').read_text())
    manifest = json.loads((ROOT / 'data/provenance.json').read_text())
    assert m['inputs'] == manifest['files']
    pairs = [read_pds(ROOT / 'data' / item['name']) for item in manifest['files']]
    (left, ml, hl), (right, mr, hr) = pairs
    for side, (raw, model, header) in zip(['LEFT', 'RIGHT'], pairs):
        assert raw.shape == (1024, 1024)
        assert re.search(r'FRAME_ID\s*=\s*"' + side + '"', header)
        assert 'MODEL_TYPE                      = CAHVOR' in header
        assert 'REFERENCE_COORD_SYSTEM_NAME     = ROVER_FRAME' in header
        assert 'REFERENCE_COORD_SYSTEM_INDEX    = (125,100,0,5,0)' in header
        assert re.search(r'PLANET_DAY_NUMBER\s*=\s*767', header)
        assert all(np.isfinite(v).all() for v in model.values())
        for axis in ['A', 'O']:
            close(np.linalg.norm(model[axis]), 1, atol=2e-6)
    baseline = np.linalg.norm(mr['C'] - ml['C'])
    assert .19 < baseline < .21
    close(baseline, m['baseline_m'])
    d = np.load(out / 'terrain.npz')
    close(d['baseline'], baseline)
    close(d['center'], ml['C'])
    basis = d['basis'];close(basis @ basis.T, np.eye(3));close(np.linalg.det(basis), 1)
    close(basis[0], (mr['C'] - ml['C']) / baseline)
    forward = ml['A'] + mr['A'];forward -= basis[0] * (forward @ basis[0]);forward /= np.linalg.norm(forward)
    close(basis[2], forward)
    f = float(d['focal']);assert f == m['rectified_focal_px'] == 1150
    yy, xx = np.mgrid[:1024, :1024]
    rays = (xx[..., None] - 511.5) / f * basis[0] + (yy[..., None] - 511.5) / f * basis[1] + basis[2]
    lo, hi = np.percentile(np.concatenate([left.ravel(), right.ravel()]), [.5, 99.5])
    maps = [];rect = []
    for (raw, model, _), side in zip(pairs, ['left', 'right']):
        image = np.uint8(np.clip((raw - lo) / (hi - lo), 0, 1) * 255)
        np.testing.assert_array_equal(image, np.array(Image.open(out / (side + '-raw.png'))))
        u, v = project(rays, model);maps.append((u, v))
        rect.append(cv2.remap(image, u.astype('float32'), v.astype('float32'), cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT))
    sift = cv2.SIFT_create()
    kl, dl = sift.detectAndCompute(rect[0], None);kr, dr = sift.detectAndCompute(rect[1], None)
    matches = cv2.BFMatcher().knnMatch(dl, dr, k=2)
    dy = np.array([kl[a.queryIdx].pt[1] - kr[a.trainIdx].pt[1] for a,b in matches if a.distance < .7*b.distance])
    inlier = dy[abs(dy - np.median(dy)) < 1.5];offset = float(np.median(inlier))
    assert abs(offset) < 2
    close(offset, m['vertical_refinement_px'])
    close(np.median(abs(inlier-offset)), m['epipolar_residual_after_px_median'])
    rect[1] = cv2.warpAffine(rect[1], np.float32([[1,0,0],[0,1,offset]]), (1024,1024), flags=cv2.INTER_CUBIC)
    for image, side in zip(rect, ['left', 'right']):
        np.testing.assert_array_equal(image, np.array(Image.open(out / (side + '.png'))))
    np.testing.assert_array_equal(d['texture'], rect[0])
    # Re-evaluate both directions from rectified source pixels; summaries are not accepted as evidence.
    params = dict(numDisparities=160, blockSize=5, P1=200, P2=800, disp12MaxDiff=-1,
                  uniquenessRatio=8, speckleWindowSize=100, speckleRange=2, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
    disparity = cv2.StereoSGBM_create(minDisparity=0, **params).compute(*rect).astype(float) / 16
    reverse = cv2.StereoSGBM_create(minDisparity=-160, **params).compute(rect[1],rect[0]).astype(float) / 16
    np.testing.assert_array_equal(d['disparity'], disparity)
    cycle = abs(disparity + cv2.remap(reverse.astype('float32'), (xx-disparity).astype('float32'), yy.astype('float32'), cv2.INTER_LINEAR, borderValue=-999))
    close(cycle, d['cycle'])
    depth = f * baseline / np.maximum(disparity, .01)
    valid = (disparity>2)&(disparity<158)&(cycle<1)&(depth>.8)&(depth<30)&(xx>170)&(yy>70)&(yy<930)
    for u,v in maps:
        valid &= (u>3)&(v>3)&(u<1020)&(v<1020)
    np.testing.assert_array_equal(d['valid'], valid)
    assert valid.sum() == m['valid_pixels']
    close(np.percentile(depth[valid],[5,50,95]), m['depth_m_percentiles'])
    close(np.percentile(cycle[valid],[50,95,100]), m['left_right_cycle_px_percentiles'])
    close(np.median(depth[valid]**2/(f*baseline)), m['one_pixel_depth_uncertainty_m_median'])
    v, faces, uv = d['vertices'], d['faces'], d['uv']
    assert len(v) == m['vertices'] and len(faces) == m['triangles']
    assert np.isfinite(v).all() and faces.min() >= 0 and faces.max() < len(v)
    assert np.issubdtype(faces.dtype, np.integer)
    assert ((uv>=0)&(uv<=1)).all()
    px = np.rint(uv[:,0]*1023).astype(int);py = np.rint((1-uv[:,1])*1023).astype(int)
    assert (px%3==0).all() and (py%3==0).all() and valid[py,px].all()
    close(v[:,2], depth[py,px]);close(v[:,0], (px-511.5)*v[:,2]/f);close(v[:,1], (py-511.5)*v[:,2]/f)
    assert (np.ptp(px[faces],axis=1)==3).all() and (np.ptp(py[faces],axis=1)==3).all()
    z = v[faces,2]
    assert (np.ptp(z,axis=1)<(.06+.035*z.min(axis=1))).all()
    assert (np.linalg.norm(np.cross(v[faces[:,1]]-v[faces[:,0]], v[faces[:,2]]-v[faces[:,0]]),axis=1)>0).all()
    lines = (out/'terrain.obj').read_text().splitlines()
    close(np.array([list(map(float,s.split()[1:])) for s in lines if s.startswith('v ')]), v, atol=6e-8)
    close(np.array([list(map(float,s.split()[1:])) for s in lines if s.startswith('vt ')]), uv, atol=6e-8)
    exported = np.array([[int(x.split('/')[0])-1 for x in s.split()[1:]] for s in lines if s.startswith('f ')])
    np.testing.assert_array_equal(exported, faces)
    assert 'map_Kd left.png' in (out/'terrain.mtl').read_text()
    ply = (out/'terrain.ply').read_text().split('end_header\n',1)
    assert f'element vertex {len(v)}' in ply[0]
    points = np.loadtxt(ply[1].splitlines())
    close(points[:,:3], v@basis+ml['C'], atol=6e-8)
    np.testing.assert_array_equal(points[:,3:], np.repeat(rect[0][py,px,None],3,axis=1))
    video = ROOT/'demo/wheatstone.mp4';assert video.is_file()
    info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
    stream = next(s for s in info['streams'] if s['codec_type']=='video')
    assert (stream['width'],stream['height'])==(1920,1080) and stream['codec_name']=='h264'
    assert stream['avg_frame_rate']=='30/1' and abs(float(info['format']['duration'])-44)<.05
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'],check=True)
    print('PASS: source hashes, camera geometry, source rectification, both stereo directions, depth, validity, mesh exports, full video decode')


if __name__=='__main__':
    main()
