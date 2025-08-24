from typing import Dict, Any, List, Tuple


def price_deviation_pct(ours: Dict[str, Any], theirs: Dict[str, Any]) -> float | None:
    try:
        a = ours.get('normalized_value')
        b = theirs.get('normalized_value')
        if a is None or b is None or b == 0:
            return None
        return round(((a - b) / b) * 100.0, 2)
    except Exception:
        return None


def amenity_overlap_pct(ours: List[str], theirs: List[str]) -> float | None:
    try:
        if not ours or not theirs:
            return None
        A = set(s.strip().lower() for s in ours if isinstance(s, str))
        B = set(s.strip().lower() for s in theirs if isinstance(s, str))
        if not A or not B:
            return None
        return round((len(A & B) / len(A | B)) * 100.0, 1)
    except Exception:
        return None


def tenancy_match_ratio(ours_cfg: Dict[str, Any], theirs_cfg: Dict[str, Any]) -> float | None:
    try:
        to = ours_cfg.get('tenancies') if isinstance(ours_cfg, dict) else None
        tt = theirs_cfg.get('tenancies') if isinstance(theirs_cfg, dict) else None
        if not isinstance(to, list) or not isinstance(tt, list) or not to or not tt:
            return None
        def keyset(lst):
            s = set()
            for t in lst:
                if isinstance(t, dict):
                    k = (t.get('duration_months') or t.get('duration') or '').__str__()
                    s.add(k)
            return s
        A = keyset(to)
        B = keyset(tt)
        if not A or not B:
            return None
        return round(len(A & B) / len(A | B), 2)
    except Exception:
        return None


def diff_properties(ours: Dict[str, Any], theirs: Dict[str, Any]) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        'summary': {},
        'mismatches': []
    }
    # Basic info
    our_basic = (ours.get('basic_info') or {}) if isinstance(ours, dict) else {}
    th_basic = (theirs.get('basic_info') or {}) if isinstance(theirs, dict) else {}
    if our_basic.get('name') and th_basic.get('name') and our_basic.get('name') != th_basic.get('name'):
        report['mismatches'].append({'path': 'basic_info.name', 'ours': our_basic.get('name'), 'theirs': th_basic.get('name')})

    # Amenities/Features overlap
    our_feats = [f.get('name') for f in (ours.get('features') or []) if isinstance(f, dict) and f.get('name')]
    th_feats = [f.get('name') for f in (theirs.get('features') or []) if isinstance(f, dict) and f.get('name')]
    report['summary']['amenity_overlap_pct'] = amenity_overlap_pct(our_feats, th_feats)

    # Configuration-level comparison by name
    our_cfgs = ours.get('configurations') or []
    th_cfgs = theirs.get('configurations') or []
    name_to_cfg = {}
    for c in th_cfgs:
        if isinstance(c, dict):
            key = c.get('name') or c.get('Basic', {}).get('Configuration Name')
            if key:
                name_to_cfg[str(key).strip().lower()] = c

    cfg_mismatch = 0
    checked = 0
    for oc in our_cfgs:
        if not isinstance(oc, dict):
            continue
        key = oc.get('name') or oc.get('Basic', {}).get('Configuration Name')
        if not key:
            continue
        match = name_to_cfg.get(str(key).strip().lower())
        checked += 1
        if not match:
            report['mismatches'].append({'path': f'configurations[{key}]', 'ours': 'present', 'theirs': 'missing'})
            cfg_mismatch += 1
            continue
        # Pricing deviation
        op = oc.get('Pricing') or {}
        tp = match.get('Pricing') or {}
        dev = price_deviation_pct(op, tp)
        if dev is not None:
            report['mismatches'].append({'path': f'configurations[{key}].Pricing.deviation_pct', 'ours': op.get('normalized_value'), 'theirs': tp.get('normalized_value'), 'delta_pct': dev})
        # Tenancy match ratio
        tmr = tenancy_match_ratio(oc, match)
        if tmr is not None:
            report['mismatches'].append({'path': f'configurations[{key}].tenancies.match_ratio', 'ratio': tmr})

    if checked:
        report['summary']['configuration_match_rate'] = round((checked - cfg_mismatch) / checked, 2)
    else:
        report['summary']['configuration_match_rate'] = None

    return report


