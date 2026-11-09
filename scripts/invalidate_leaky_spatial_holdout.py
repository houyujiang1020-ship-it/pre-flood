"""Record that the first foundation spatial comparison used a holdout-exposed initializer."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / 'experiments/louisiana-east-spatial-holdout-20260926/evaluation.json'


def main():
    value = json.loads(RESULT.read_text(encoding='utf-8'))
    value['protocol_verified'] = False
    value['promotion'] = 'invalidated'
    value['rejection_reason'] = ('The E3c initialization checkpoint was trained on all Louisiana-East tiles, '
                                 'including the 92-tile spatial holdout.')
    value['leakage_scope'] = ('Random-initialization result remains a valid fixed-epoch baseline; the first '
                              'foundation-initialized result is not a generalization estimate.')
    value['replacement_required'] = 'Retrain foundation without the holdout, then repeat the four-class run.'
    RESULT.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'evaluation': str(RESULT), 'promotion': value['promotion'],
                      'reason': value['rejection_reason']}), flush=True)


if __name__ == '__main__':
    main()
