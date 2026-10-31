"""Classical vision baseline only: no pretrained NVIDIA models or trained weights bundled."""
import numpy as np

def compare_reference(reference_gray, live_gray, *, threshold=40):
    import cv2
    if reference_gray.shape!=live_gray.shape:raise ValueError('images must be pose-aligned to same shape first')
    if reference_gray.ndim!=2:raise ValueError('grayscale input required')
    # Pixel difference is sensitive to pose and illumination; it is NOT a calibrated defect probability.
    absdiff=cv2.absdiff(reference_gray.astype('uint8'),live_gray.astype('uint8'))
    fraction=float(np.mean(absdiff>threshold))
    return {'difference_fraction':fraction,'anomaly_candidate':fraction>0.03,'threshold':threshold,'method':'pixel_difference_baseline', 'calibrated':False}


def silhouette_iou(reference_mask,live_mask):
    if reference_mask.shape!=live_mask.shape:raise ValueError('registered masks required')
    a=np.asarray(reference_mask)>0;b=np.asarray(live_mask)>0
    union=int(np.count_nonzero(a|b))
    if union==0:raise ValueError('empty segmentation')
    return float(np.count_nonzero(a&b)/union)


def cad_projection_from_stl(path,view='top',pixels=256):
    """Orthographic STL triangle rasterization (binary 2D silhouette).
    Captures projected concavities but NOT depth, internal tolerances, calibration or 3D pose.
    """
    import trimesh
    mesh=trimesh.load(path,force='mesh')
    idx={'top':(0,1),'front':(0,2),'side':(1,2)}[view]
    pts=np.asarray(mesh.vertices)[:,list(idx)]
    minv=pts.min(axis=0);span=np.ptp(pts,axis=0)
    if min(span)<=0:raise ValueError('degenerate CAD projection')
    # Isotropic scale prevents distortion of aspect ratio.
    scale=pixels*0.8/max(span)
    scaled=(pts-minv)*scale
    scaled+=(pixels-scaled.max(axis=0))/2
    import cv2
    canvas=np.zeros((pixels,pixels),dtype='uint8')
    vertices=np.rint(scaled).astype('int32')
    for tri in mesh.faces:
        cv2.fillConvexPoly(canvas,vertices[tri],255)
    return canvas
