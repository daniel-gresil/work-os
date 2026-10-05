"""Create one mill-blank style in ERPNext production from the sheets: supplier, attributes, item group,
item template, one variant per colorway x size, and buying prices from the SPD Costing Database.
Idempotent: every record is checked before it is created. Default is a dry run.

usage: source ~/.cache/claude-secrets/work-os/env.sh && python3 blank_setup.py Optima 47832 [--apply]
"""
import sys
import gs, erp

TRACKER = '1eFvKttDYmZdJlYouPPeuPAYaFSimKLyQSk_fPsjey7k'
COSTING = '11hWeBKGV8cXcUh9QJqQZDmooBUB49pZnsOLlDM5hWOA'
SIZES = ['XXS', 'XS', 'SM', 'MD', 'LG', 'XL', '2X', '3X', '4X', '5X', '6X']
# Costing Database price columns (ids 1007-1014) cover XS..4X; XXS/5X/6X have no supplier price yet
COST_COLS = {'XS': 1007, 'SM': 1008, 'MD': 1009, 'LG': 1010, 'XL': 1011, '2X': 1012, '3X': 1013, '4X': 1014}
ITEM_GROUP = 'Mill Blank'
SUPPLIER_GROUP = 'Mill'
ATTR_COLOR, ATTR_SIZE = 'Blank Colorway', 'Blank Size'
PRICE_LIST = 'Standard Buying'

apply = '--apply' in sys.argv
actions = []


def do(label, fn):
    actions.append(label)
    print(('APPLY ' if apply else 'would ') + label)
    if apply: return fn()


def abbr(v):
    return str(v).upper().replace(' ', '-')


def read_sheets(supplier, style):
    """Return ({colorway: color_group}, {color_group: {size: cost}}, style_name, content, weight)."""
    colorways = {}
    for r in gs.get(TRACKER, 'Inventory!A5:Z176'):
        if len(r) > 6 and r[1] == supplier and str(r[4]) == style and r[5] != '':
            colorways[str(r[5]).strip()] = str(r[6]).strip()
    rows = gs.get(COSTING, 'Costing Database!A1:BZ103')
    col = {rows[0][i]: i for i in range(len(rows[0])) if rows[0][i] != ''}
    costs, name, content, weight = {}, None, None, None
    for r in rows[3:]:
        g = lambda i: r[col[i]] if len(r) > col[i] else ''
        if g(1001) == supplier and str(g(1002)) == style:
            # several rows per color group (plain blank, cropped, muscle tee, size-up); the first is the plain blank
            costs.setdefault(str(g(1003)).strip(), {s: g(c) for s, c in COST_COLS.items() if isinstance(g(c), (int, float)) and g(c) > 0})
            name, content, weight = name or g(1055), content or g(1004), weight or g(1005)
    return colorways, costs, name, content, weight


def ensure_group(doctype, name, parent_field, parent):
    if not erp.exists(doctype, name):
        do(f'create {doctype} "{name}"', lambda: erp.insert({'doctype': doctype, doctype.lower().replace(' ', '_') + '_name': name, parent_field: parent, 'is_group': 0}))


def ensure_attribute(name, values):
    if erp.exists('Item Attribute', name):
        have = {v['attribute_value'] for v in erp.get_doc('Item Attribute', name).get('item_attribute_values', [])}
        missing = [v for v in values if v not in have]
        if missing:
            doc = erp.get_doc('Item Attribute', name)
            rows = doc['item_attribute_values'] + [{'attribute_value': v, 'abbr': abbr(v)} for v in missing]
            do(f'add {len(missing)} value(s) to Item Attribute "{name}": {missing}', lambda: erp.update('Item Attribute', name, {'item_attribute_values': rows}))
    else:
        do(f'create Item Attribute "{name}" with {len(values)} values', lambda: erp.insert({'doctype': 'Item Attribute', 'attribute_name': name, 'item_attribute_values': [{'attribute_value': v, 'abbr': abbr(v)} for v in values]}))


def main(supplier, style):
    colorways, costs, style_name, content, weight = read_sheets(supplier, style)
    if not colorways: sys.exit(f'no tracker rows for {supplier} {style}')
    if not costs: sys.exit(f'no Costing Database rows for {supplier} {style}')
    print(f'{supplier} {style} "{style_name}" {content} {weight} oz: {len(colorways)} colorways {sorted(colorways)}; cost groups {sorted(costs)}')
    missing_cost = [c for c, grp in colorways.items() if grp not in costs]
    if missing_cost: print('WARNING no cost for color groups of', missing_cost)

    ensure_group('Supplier Group', SUPPLIER_GROUP, 'parent_supplier_group', 'All Supplier Groups')
    if not erp.exists('Supplier', supplier):
        do(f'create Supplier "{supplier}"', lambda: erp.insert({'doctype': 'Supplier', 'supplier_name': supplier, 'supplier_group': SUPPLIER_GROUP, 'supplier_type': 'Company', 'country': 'United States'}))
    ensure_group('Item Group', ITEM_GROUP, 'parent_item_group', 'All Item Groups')
    ensure_attribute(ATTR_SIZE, SIZES)
    ensure_attribute(ATTR_COLOR, sorted(colorways))

    template = f'{abbr(supplier)}-{style}'
    if not erp.exists('Item', template):
        do(f'create Item template "{template}" ({supplier} {style} {style_name})', lambda: erp.insert({
            'doctype': 'Item', 'item_code': template, 'item_name': f'{supplier} {style} {style_name}', 'item_group': ITEM_GROUP,
            'stock_uom': 'Nos', 'is_stock_item': 1, 'has_variants': 1, 'variant_based_on': 'Item Attribute',
            'description': f'{supplier} {style} {style_name}. {content}, {weight} oz.',
            'brand': None, 'supplier_items': [{'supplier': supplier, 'supplier_part_no': style}],
            'attributes': [{'attribute': ATTR_COLOR}, {'attribute': ATTR_SIZE}]}))

    existing = {r['name'] for r in erp.get_list('Item', filters={'variant_of': template})} if erp.exists('Item', template) else set()
    created = 0
    for color in sorted(colorways):
        for size in SIZES:
            code = f'{template}-{abbr(color)}-{size}'
            if code in existing: continue
            created += 1
            if apply:
                erp.insert({'doctype': 'Item', 'item_code': code, 'item_name': f'{supplier} {style} {color} {size}', 'variant_of': template,
                            'item_group': ITEM_GROUP, 'stock_uom': 'Nos', 'is_stock_item': 1, 'variant_based_on': 'Item Attribute',
                            'attributes': [{'attribute': ATTR_COLOR, 'attribute_value': color}, {'attribute': ATTR_SIZE, 'attribute_value': size}]})
    actions.append(f'variants {created}')
    print(f'{"APPLY" if apply else "would"} create {created} variants (e.g. {template}-{abbr(sorted(colorways)[0])}-MD), {len(existing)} already exist')

    priced = {r['item_code'] for r in erp.get_list('Item Price', fields=('item_code',), filters={'price_list': PRICE_LIST, 'item_code': ['like', template + '-%']})}
    n = 0
    for color, grp in colorways.items():
        for size, rate in costs.get(grp, {}).items():
            code = f'{template}-{abbr(color)}-{size}'
            if code in priced: continue
            n += 1
            if apply:
                erp.insert({'doctype': 'Item Price', 'item_code': code, 'price_list': PRICE_LIST, 'price_list_rate': rate, 'supplier': supplier})
    print(f'{"APPLY" if apply else "would"} create {n} buying prices on "{PRICE_LIST}" (per color group: ' + '; '.join(f'{g}: ' + ', '.join(f'{s} {r}' for s, r in c.items()) for g, c in costs.items()) + ')')
    actions.append(f'prices {n}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
    print('\nDRY RUN, nothing written. Re-run with --apply.' if not apply else '\nDone.')
