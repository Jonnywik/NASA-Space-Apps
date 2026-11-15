import csv
import html
import io
import json

from . import templates_en, templates_fil


def scalar(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list, bool)) else str(value)


def leaves(value, path=''):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from leaves(item, f'{path}.{key}' if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from leaves(item, f'{path}[{index}]')
    else:
        yield path, value


def missing(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if item is None and not key.lower().endswith('reason'):
                reasons = value.get('reasons') or {}
                reason = value.get(key + 'Reason') or reasons.get(key) or value.get('reason') or 'no reason was provided by the source'
                yield key, scalar(reason)
            elif isinstance(item, (dict, list)):
                yield from missing(item)
    elif isinstance(value, list):
        for item in value:
            yield from missing(item)


def build(spot, lang):
    template = templates_en if lang == 'en' else templates_fil
    sentences = []
    for key, label in template.LABELS.items():
        stream = spot['streams'][key]
        if stream['value'] is None:
            sentences.append(f"{label}: {template.UNAVAILABLE} {stream['reason']}.")
        else:
            value = stream['value']
            if key == 'place':
                place = value.get('barangay') or {}
                city = value.get('city') or {}
                detail = ', '.join(p['name'] for p in (place, city) if p.get('name'))
            elif key == 'nisar':
                count = value.get('floodCount')
                count = scalar(count) if count is not None else f"{template.UNAVAILABLE} {value.get('floodCountReason') or 'no reason was provided by the source'}"
                detail = template.FLOOD.format(count=count, valid=value.get('validCount'))
            elif key == 'priority':
                detail = template.PRIORITY_YES if value else template.PRIORITY_NO
            elif key == 'exposure':
                def amount(field, reason):
                    v = value.get(field)
                    return scalar(v) if v is not None else f"{template.UNAVAILABLE} {reason or 'the source has no supported estimate'}"
                detail = template.EXPOSURE.format(area=amount('areaKm2', None),
                    population=amount('population', value.get('populationReason')),
                    buildings=amount('buildings', value.get('buildingsReason')))
            elif key == 'rainfall':
                rows = [r for r in value if r.get('prior7DayMm') is not None]
                if rows:
                    latest = max(rows, key=lambda r: r['date'])
                    detail = template.RAINFALL.format(rain=latest['prior7DayMm'], date=latest['date'])
                else:
                    detail = f"{template.UNAVAILABLE} no complete prior-pass rainfall window is available"
            elif key == 'motion':
                rows = [(date, displacement) for date, displacement in zip(value.get('epochs', []), value.get('displacementMm', [])) if displacement is not None]
                if rows:
                    date, displacement = rows[-1]
                    detail = template.MOTION.format(date=date, displacement=displacement)
                else:
                    detail = f"{template.UNAVAILABLE} no valid displacement epoch is available"
            sentences.append(f'{label}: {detail}.')
            sentences.extend(f'{label} ({key}): {template.UNAVAILABLE} {reason}.'
                             for key, reason in missing(stream['value']))
    return {'language': lang, 'translationStatus': 'pending native-speaker review' if lang == 'fil' else None,
            'dataKind': spot['dataKind'], 'sentences': sentences, 'facts': spot,
            'source': spot['source'], 'generatedAt': spot['generatedAt'],
            'warnings': spot['warnings'], 'limitations': spot['limitations']}


def csv_text(briefing):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['field', 'value', 'units', 'source', 'dataKind'])
    facts = briefing['facts']
    for key in ('dataKind', 'area', 'lon', 'lat'):
        writer.writerow([key, facts.get(key, ''), 'degrees' if key in ('lon', 'lat') else '', 'request' if key in ('lon', 'lat') else '', facts.get('dataKind', '')])
    for name, stream in briefing['facts']['streams'].items():
        items = list(leaves(stream['value'], name)) if stream['value'] is not None else [(name, None)]
        for field, value in items:
            text = '' if value is None else scalar(value)
            if isinstance(value, str) and text.lstrip().startswith(('=', '+', '-', '@')):
                text = "'" + text
            writer.writerow([field, text, stream.get('units') or '', scalar(stream['source']) if stream['source'] else '', stream['dataKind'] or ''])
        if stream['reason']:
            reason = stream['reason']
            if reason.lstrip().startswith(('=', '+', '-', '@')):
                reason = "'" + reason
            writer.writerow([name + '.reason', reason, '', '', ''])
    return out.getvalue()


def html_text(briefing):
    e = html.escape
    badge = '<strong>SYNTHETIC DEMO DATA</strong>' if briefing['dataKind'] == 'synthetic' else ''
    paragraphs = ''.join(f'<p>{e(s)}</p>' for s in briefing['sentences'])
    sources = ''.join(f'<li>{e(k)}: {e(scalar(v["source"]))}; {e(scalar(v["nativeResolution"]))}</li>'
                      for k, v in briefing['facts']['streams'].items())
    limits = ''.join(f'<li>{e(x)}</li>' for x in briefing['limitations'] + briefing['warnings'])
    review = '<p>Translation: pending native-speaker review</p>' if briefing['language'] == 'fil' else ''
    return f'<!doctype html><html lang="{e(briefing["language"])}"><head><meta charset="utf-8"><title>Place briefing</title></head><body>{badge}<h1>Place briefing</h1>{review}{paragraphs}<h2>Sources</h2><ul>{sources}</ul><h2>Limitations</h2><ul>{limits}</ul></body></html>'
