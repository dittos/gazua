# -*- encoding: utf-8 -*-
import sys
import json
import getpass
import pip._vendor.requests as requests


def login(config):
    email = raw_input('Email: ')
    password = getpass.getpass()
    resp = requests.post('https://api.korbit.co.kr/v1/oauth2/access_token', data={
        'client_id': config['korbit_client_id'],
        'client_secret': config['korbit_client_secret'],
        'grant_type': 'password',
        'username': email,
        'password': password,
    })
    resp.raise_for_status()
    with open('credentials.json', 'w') as fp:
        json.dump(resp.json(), fp)
    print 'Successfully written credentials.json'


def refresh_token(config):
    print 'Refreshing token...'
    with open('credentials.json') as fp:
        credentials = json.load(fp)
    resp = requests.post('https://api.korbit.co.kr/v1/oauth2/access_token', data={
        'client_id': config['korbit_client_id'],
        'client_secret': config['korbit_client_secret'],
        'grant_type': 'refresh_token',
        'refresh_token': credentials['refresh_token'],
    })
    resp.raise_for_status()
    print 'Token refreshed.'
    with open('credentials.json', 'w') as fp:
        json.dump(resp.json(), fp)
        print 'Successfully written credentials.json'


def push(config, payload):
    resp = requests.post('https://api.pushbullet.com/v2/pushes', json=payload, headers={
        'Access-Token': config['pushbullet_access_token'],
    })
    resp.raise_for_status()


def work(config):
    refresh_token(config)
    with open('credentials.json') as fp:
        credentials = json.load(fp)

    try:
        fp = open('state.json')
    except IOError:
        state = {
            'open_orders': {},
        }
    else:
        with fp:
            state = json.load(fp)
    
    print 'Check open orders change'
    current_open_orders = {}
    for currency_pair in ('btc_krw', 'eth_krw'):
        resp = requests.get('https://api.korbit.co.kr/v1/user/orders/open', headers={
            'Authorization': 'Bearer {}'.format(credentials['access_token']),
        }, params={
            'currency_pair': currency_pair,
        })
        resp.raise_for_status()
        current_open_orders.update(dict((order['id'], order) for order in resp.json()))
    
    changes = []
    for id, order in current_open_orders.items():
        if id not in state['open_orders']:
            changes.append((None, order))
        else:
            prev_order = state['open_orders'][id]
            if order != prev_order:
                changes.append((prev_order, order))
    for id, prev_order in state['open_orders'].items():
        if id not in current_open_orders:
            changes.append((prev_order, None))
    
    closed_orders = [prev for (prev, cur) in changes if cur is None]
    if closed_orders:
        # check status for disappeared open orders (could be deleted)
        resp = requests.get('https://api.korbit.co.kr/v1/user/orders', headers={
            'Authorization': 'Bearer {}'.format(credentials['access_token']),
        }, params={
            'id': [order['id'] for order in closed_orders],
        })
        resp.raise_for_status()
        not_deleted_order_ids = set(order['id'] for order in resp.json())
        closed_orders = [order for order in closed_orders if order['id'] in not_deleted_order_ids]

    if closed_orders:
        push(config, {
            'type': 'note',
            'title': u'[Korbit] 체결됨',
            'body': '\n'.join(
                json.dumps(order, indent=2, ensure_ascii=False)
                for order in closed_orders
            ),
        })

    state['open_orders'] = current_open_orders

    with open('state.json', 'w') as fp:
        json.dump(state, fp)


def main():
    with open('./config.json') as fp:
        config = json.load(fp)
    if len(sys.argv) >= 2 and sys.argv[1] == 'login':
        login(config)
    else:
        work(config)


if __name__ == '__main__':
    main()
