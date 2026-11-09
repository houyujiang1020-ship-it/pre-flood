"""Small NumPy-only road morphology diagnostics (not GIS entity analysis)."""
import numpy as np

def skeletonize(mask):
    image=np.pad(np.asarray(mask,dtype=bool),1)
    while True:
        changed=False
        for phase in (0,1):
            p=image[1:-1,1:-1]
            n=[image[:-2,1:-1],image[:-2,2:],image[1:-1,2:],image[2:,2:],image[2:,1:-1],image[2:,:-2],image[1:-1,:-2],image[:-2,:-2]]
            count=sum(x.astype(np.uint8) for x in n)
            transitions=sum((~n[i]&n[(i+1)%8]).astype(np.uint8) for i in range(8))
            if phase==0:condition=~(n[0]&n[2]&n[4]) & ~(n[2]&n[4]&n[6])
            else:condition=~(n[0]&n[2]&n[6]) & ~(n[0]&n[4]&n[6])
            remove=p&(count>=2)&(count<=6)&(transitions==1)&condition
            if remove.any():p[remove]=False;changed=True
        if not changed:return image[1:-1,1:-1]

def components(mask):
    """8-connected component labels via row runs and union-find."""
    mask=np.asarray(mask,dtype=bool);parent=[0];runs=[];prev=[]
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[b]=a
    for y,row in enumerate(mask):
        edges=np.diff(np.r_[False,row,False].astype(np.int8))
        starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)-1
        current=[];j=0
        for start,end in zip(starts,ends):
            index=len(parent);parent.append(index);current.append((int(start),int(end),index));runs.append((y,int(start),int(end),index))
            while j<len(prev) and prev[j][1]<start-1:j+=1
            k=j
            while k<len(prev) and prev[k][0]<=end+1:union(index,prev[k][2]);k+=1
        prev=current
    labels=np.zeros(mask.shape,dtype=np.int32);mapping={}
    for y,start,end,index in runs:
        r=find(index)
        if r not in mapping:mapping[r]=len(mapping)+1
        labels[y,start:end+1]=mapping[r]
    return labels,len(mapping)

def dilate_one(mask):
    p=np.pad(mask,1);h,w=mask.shape
    return np.logical_or.reduce([p[i:i+h,j:j+w] for i in range(3) for j in range(3)])

def morphology(gt,pred,valid=None):
    if valid is not None:gt=gt&valid;pred=pred&valid
    sk=skeletonize(gt);gl,gc=components(gt);pl,pc=components(pred)
    paired=np.stack((gl[gt&pred],pl[gt&pred]),axis=1)
    pairs=np.unique(paired,axis=0) if paired.size else np.empty((0,2),dtype=int)
    matched_gt=len(np.unique(pairs[:,0]));fragments=len(pairs)
    psizes=np.bincount(pl.ravel())[1:]
    return {'gt_components':gc,'pred_components':pc,'pred_components_ge3pixels':int((psizes>=3).sum()),'gt_skeleton_pixels':int(sk.sum()),'skeleton_covered_pixels':int((sk&pred).sum()),'skeleton_covered_within_1px':int((sk&dilate_one(pred)).sum()),'gt_components_matched':matched_gt,'matched_fragment_pairs':fragments,'excess_matched_fragments':fragments-matched_gt,'unmatched_pred_components':pc-len(np.unique(pairs[:,1])),'skeleton_recall':float((sk&pred).sum()/sk.sum()) if sk.any() else None,'fragments_per_matched_gt':fragments/matched_gt if matched_gt else None,'uncovered_gt_fraction':(gc-matched_gt)/gc if gc else None}
