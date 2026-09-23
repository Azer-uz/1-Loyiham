from fastapi import APIRouter, HTTPException
from moysklad_client import ms_client

router = APIRouter()

@router.get("/test")
async def test_moysklad():
    """MoySklad API bilan to'g'ridan-to'g'ri test"""
    try:
        # 1. Oxirgi 5 ta otgruzka
        demands = await ms_client.get_demands(limit=5)
        demands_list = []
        for d in demands.get('rows', []):
            demands_list.append({
                'id': d.get('id'),
                'name': d.get('name'),
                'moment': d.get('moment'),
                'sum': d.get('sum', 0) / 100,
                'agent': d.get('agent', {}).get('name', 'Nomaʼlum'),
            })

        # 2. Oxirgi 5 ta mijoz
        customers = await ms_client.search_counterparties('')
        customers_list = []
        for c in customers.get('rows', [])[:5]:
            customers_list.append({
                'id': c.get('id'),
                'name': c.get('name'),
                'phone': c.get('phone'),
                'balance': c.get('balance', 0) / 100,
            })

        return {
            'success': True,
            'demands': {
                'total': demands.get('meta', {}).get('size', 0),
                'last_5': demands_list,
            },
            'customers': {
                'total': customers.get('meta', {}).get('size', 0),
                'last_5': customers_list,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
