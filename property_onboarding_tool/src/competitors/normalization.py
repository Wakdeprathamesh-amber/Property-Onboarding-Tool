from typing import Dict, Any

def normalize_currency(amount: Any, unit: str | None) -> tuple[float | None, str | None, str | None]:
    """Normalize amount and unit to numeric and ISO currency with period (PW/PM)."""
    if amount is None:
        return None, None, unit
    text = str(amount).strip()
    currency = None
    if text.startswith('£'):
        currency = 'GBP'
        text = text.replace('£', '')
    elif text.startswith('$'):
        currency = 'USD'
        text = text.replace('$', '')
    elif text.startswith('€'):
        currency = 'EUR'
        text = text.replace('€', '')
    try:
        value = float(text.replace(',', ''))
    except Exception:
        return None, currency, unit
    period = None
    if unit:
        u = unit.strip().lower()
        if 'week' in u or 'pw' in u:
            period = 'PW'
        elif 'month' in u or 'pm' in u:
            period = 'PM'
    return value, currency, period


def normalize_tenancy_duration(text: Any) -> int | None:
    """Return duration in months if possible."""
    if text is None:
        return None
    s = str(text).lower()
    import re
    # 44 weeks, 51 weeks, 12 months
    m = re.search(r"(\d{1,3})\s*(week|wks|wk)s?", s)
    if m:
        weeks = int(m.group(1))
        return round(weeks / 4.345)  # approx months
    m = re.search(r"(\d{1,3})\s*(month|mo)s?", s)
    if m:
        return int(m.group(1))
    return None


def normalize_property_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort normalization: currency units, tenancy durations, numeric types."""
    if not isinstance(data, dict):
        return {}
    out = dict(data)
    # Normalize configurations pricing
    configs = out.get('configurations')
    if isinstance(configs, list):
        for cfg in configs:
            if not isinstance(cfg, dict):
                continue
            pricing = cfg.get('Pricing') or cfg.get('pricing') or {}
            if isinstance(pricing, dict):
                base = pricing.get('base') or pricing.get('base_price') or pricing.get('Base Price')
                unit = pricing.get('unit') or pricing.get('Unit') or pricing.get('billing_unit')
                value, currency, period = normalize_currency(base, unit)
                if value is not None:
                    pricing['normalized_value'] = value
                if currency:
                    pricing['currency'] = currency
                if period:
                    pricing['period'] = period
                cfg['Pricing'] = pricing
            # Normalize tenancies if present
            tenancies = cfg.get('tenancies')
            if isinstance(tenancies, list):
                for t in tenancies:
                    if not isinstance(t, dict):
                        continue
                    dur = t.get('duration') or t.get('Duration')
                    months = normalize_tenancy_duration(dur)
                    if months is not None:
                        t['duration_months'] = months
    return out


