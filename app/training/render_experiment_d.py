"""Render D probability comparison and learning curves with bundled matplotlib."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
def main():
    loc=json.loads((ROOT/'experiments/diagnostics/experiment-d-preflight-20260912/run-location.json').read_text());out=ROOT/loc['output_dir']
    folder=ROOT/'experiments/diagnostics/experiment-d-probability-20260912';data=json.loads((folder/'probability-comparison.json').read_text())
    classes=list(data['models']['old_sampler'])
    fig,axes=plt.subplots(4,2,figsize=(13,15),layout='constrained')
    for i,c in enumerate(classes):
        for model,style in [('old_sampler','--'),('experiment_d','-')]:
            v=data['models'][model][c]
            for kind,color in [('positive','#cf5c36'),('negative','#277b9a')]:
                axes[i,0].stairs(np.array(v[kind+'_histogram'])/v[kind+'_count'],v['histogram_edges'],label=model+' GT '+kind,color=color,linestyle=style,linewidth=1.5)
            rows=v['threshold_table'];color='#3166a1' if model=='old_sampler' else '#c35c30'
            axes[i,1].plot([r['recall'] for r in rows],[r['precision'] if r['precision'] is not None else 1 for r in rows],label=f"{model} AP={v['average_precision_exact_ties']:.3f}",color=color,linestyle=style)
            for threshold,marker in [(.5,'o'),([.54,.45,.18,.25][i],'s')]:
                r=min(rows,key=lambda x:abs(x['threshold']-threshold))
                if r['precision'] is not None:axes[i,1].scatter(r['recall'],r['precision'],marker=marker,color=color,s=25)
        axes[i,0].set(title=c,xlim=(0,1),ylim=(1e-6,1),yscale='log',xlabel='Probability',ylabel='Fraction within GT group (log)')
        axes[i,1].set(title='PR: circles t=0.5; squares frozen thresholds',xlim=(0,1),ylim=(0,1),xlabel='Recall',ylabel='Precision')
        for ax in axes[i]:ax.grid(alpha=.15);ax.legend(fontsize=8)
    fig.suptitle('Germany development validation only | old sampler vs road Tversky D\nAP uses exact tied-score ranking; drawn PR curve uses threshold grid 0.01',fontsize=12)
    fig.savefig(folder/'probability-comparison.png',dpi=150);plt.close(fig)
    h=json.loads((out/'history.json').read_text());epochs=[x['epoch'] for x in h]
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    axes[0,0].plot(epochs,[x['train_loss'] for x in h]);axes[0,0].set(title='Training objective BCE + replacement overlap',ylabel='Loss')
    axes[0,1].plot(epochs,[x['validation']['loss'] for x in h]);axes[0,1].set(title='Validation loss (BCE only, original protocol)',ylabel='Loss')
    for c in classes:
        axes[1,0].plot(epochs,[x['validation']['class_iou'][c] for x in h],label=c)
        axes[1,1].plot(epochs,[x['training_metrics']['class_iou'][c] for x in h],label=c)
    axes[1,0].set(title='Validation IoU, threshold0.5',ylabel='IoU');axes[1,1].set(title='Online sampled training IoU, threshold0.5',ylabel='IoU')
    for ax in axes.flat:ax.set_xlabel('Epoch');ax.grid(alpha=.2)
    axes[1,0].legend(fontsize=8);axes[1,1].legend(fontsize=8)
    fig.savefig(out/'learning-curves.png',dpi=150)
    print('Rendered D figures')
if __name__=='__main__':main()
