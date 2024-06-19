import dash
from dash import dcc, html
from dash.dependencies import Output, Input, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import requests
from datetime import datetime
import json
import os

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])


# Initial balance for currencies
orders = []
fake_balances = {'USDT': 1000, 'BTC': 0, 'ETH': 0, 'LTC': 0, 'XRP': 0}

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Order Trade & Balance Simulation"), className="mb-2")
    ]),
    dbc.Row([
        dbc.Col(dcc.Dropdown(
            id='time-frame-selector', # Time frames for refresh cycle
            options=[
                {'label': '1 Minute', 'value': '1m'},
                {'label': '5 Minutes', 'value': '5m'},
                {'label': '15 Minutes', 'value': '15m'},
                {'label': '1 Hour', 'value': '1h'},
                {'label': '12 Hours', 'value': '12h'}
            ],
            value='5m', # Default time frame for refresh
            clearable=False
        ), className="mb-4")
    ]),
    dbc.Row([
        dbc.Col(html.Label("Initial Balance (USDT)"), width=3),
        dbc.Col(html.Label("Crypto Pair"), width=3),
        dbc.Col(html.Label("Balance (USDT)"), width=3),
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Input(id='balance', type='number', value=1000, min=0, step=1),
        ], width=3),
        dbc.Col([
            dcc.Dropdown(
                id='pair-selector',
                options=[
                    {'label': 'BTC/USDT', 'value': 'BTCUSDT'},
                    {'label': 'ETH/BTC', 'value': 'ETHBTC'},
                    {'label': 'LTC/USDT', 'value': 'LTCUSDT'},
                    {'label': 'XRP/USDT', 'value': 'XRPUSDT'}
                ],
                value='BTCUSDT',
                clearable=False
            ),
        ], width=3),
        dbc.Col([
            html.Div(id='balance-output')
        ], width=3)
    ]),
    dbc.Row([
        dbc.Col(html.Label("Balances:"), width=2),
        dbc.Col(html.Div(id='btc-balance-output'), width=2),
        dbc.Col(html.Div(id='eth-balance-output'), width=2),
        dbc.Col(html.Div(id='ltc-balance-output'), width=2),
        dbc.Col(html.Div(id='xrp-balance-output'), width=2),
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Dropdown(
                id='order-type-selector',
                options=[
                    {'label': 'Buy Limit', 'value': 'BUY_LIMIT'},
                    {'label': 'Sell Limit', 'value': 'SELL_LIMIT'},
                    {'label': 'Market Buy', 'value': 'MARKET_BUY'},
                    {'label': 'Market Sell', 'value': 'MARKET_SELL'}
                ],
                value='BUY_LIMIT',
                clearable=False
            ),
            dcc.Input(id='order-price', type='number', placeholder='Order Price', step=0.01),
            dcc.Input(id='order-quantity', type='number', placeholder='Order Quantity', step=0.01),
            html.Button('Submit Order', id='submit-order', n_clicks=0)
        ], width=6)
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='live-crypto-chart'))
    ]),
    dbc.Row([
        dbc.Col(html.H3("Order History")),
        dbc.Col(html.Div(id='order-history'))
    ]),
    dbc.Row([
        dbc.Col(html.Div(id='notification', style={'color': 'red'}))
    ]),
    dcc.Interval(
        id='interval-component',
        interval=60*1000,
        n_intervals=0
    )
])

# Time frames in miliseconds
time_frame_to_interval = {
    '1m': 60*1000,      # 1 minute
    '5m': 5*60*1000,    # 5 minutes
    '15m': 15*60*1000,  # 15 minutes
    '1h': 60*60*1000,   # 1 hour
    '12h': 12*60*60*1000 # 12 hours
}

def get_crypto_data(pair, interval):
    # Binance API for historical data
    try:
        url = f'https://api.binance.com/api/v3/klines?symbol={pair}&interval={interval}&limit=100'
        response = requests.get(url)
        data = response.json()
        close_prices = [float(candle[4]) for candle in data]
        timestamps = [datetime.fromtimestamp(candle[0] / 1000) for candle in data]
        return timestamps, close_prices
    except Exception as e:
        print(f"Error fetching data for {pair}: {e}")
        return [], []

def check_limit_orders(prices):
    # Check/update the status of pending orders based on current prices
    notifications = []
    global orders
    global fake_balances

    for order in orders:
        if order['status'] == 'Pending':
            current_price = prices[order['pair']][-1] if prices[order['pair']] else None
            if current_price is not None:
                # Process Buy Limit order
                if order['order_type'] == 'BUY_LIMIT' and current_price <= order['price']:
                    order['status'] = 'Filled'
                    order['order_complete_date'] = datetime.now()
                    fake_balances['USDT'] -= order['total']
                    fake_balances[order['pair'][:3]] += order['quantity']
                    notifications.append(f"Order Filled: {order['order_type']} {order['pair']} at {order['price']} for {order['quantity']}")
                # Process Sell Limit Order
                elif order['order_type'] == 'SELL_LIMIT' and current_price >= order['price']:
                    order['status'] = 'Filled'
                    order['order_complete_date'] = datetime.now()
                    fake_balances[order['pair'][:3]] -= order['quantity']
                    fake_balances['USDT'] += order['total']
                    notifications.append(f"Order Filled: {order['order_type']} {order['pair']} at {order['price']} for {order['quantity']}")
    
    return notifications

@app.callback(
    Output('live-crypto-chart', 'figure'),
    Output('interval-component', 'interval'),
    Output('order-history', 'children'),
    Output('notification', 'children'),
    Output('submit-order', 'disabled'),
    Output('balance-output', 'children'),
    Output('btc-balance-output', 'children'),
    Output('eth-balance-output', 'children'),
    Output('ltc-balance-output', 'children'),
    Output('xrp-balance-output', 'children'),
    [Input('time-frame-selector', 'value'), Input('interval-component', 'n_intervals'), Input('submit-order', 'n_clicks'), Input('order-type-selector', 'value'), Input('order-price', 'value'), Input('order-quantity', 'value'), Input('balance', 'value'), Input({'type': 'cancel-button', 'index': dash.dependencies.ALL}, 'n_clicks')],
    [State('pair-selector', 'value'), State('submit-order', 'n_clicks_timestamp'), State({'type': 'cancel-button', 'index': dash.dependencies.ALL}, 'n_clicks_timestamp')]
)
def update_chart_and_balances(selected_time_frame, n_intervals, submit_n_clicks, order_type, order_price, order_quantity, balance, cancel_n_clicks_list, selected_pair, submit_order_timestamp, cancel_order_timestamps):
    # Updates the dashbord with the latest data.
    global orders
    global fake_balances

    # Update the balance via user input
    if balance is not None:
        fake_balances['USDT'] = balance

    # List of tradinig pairs
    pairs = ['BTCUSDT', 'ETHBTC', 'LTCUSDT', 'XRPUSDT']
    prices = {}
    timestamps = {}

    for pair in pairs:
        timestamps[pair], prices[pair] = get_crypto_data(pair, selected_time_frame)

    current_price = prices[selected_pair][-1] if prices[selected_pair] else 0
    order_price = order_price if order_price is not None else current_price
    order_quantity = order_quantity if order_quantity is not None else 0

    # Calculate total cost for order
    order_total_cost = order_price * order_quantity


    # Determine if the submit button should be disabled or not
    button_disabled = False
    if order_type in ['BUY_LIMIT', 'MARKET_BUY']:
        if fake_balances['USDT'] < order_total_cost or order_total_cost <= 0:
            button_disabled = True
    elif order_type in ['SELL_LIMIT', 'MARKET_SELL']:
        if fake_balances.get(selected_pair[:3], 0) < order_quantity or order_quantity <= 0:
            button_disabled = True

    # Context information for callback
    ctx = dash.callback_context

    # Order submission
    if ctx.triggered and ctx.triggered[0]['prop_id'] == 'submit-order.n_clicks' and submit_n_clicks > 0 and (not cancel_order_timestamps or submit_order_timestamp > max(filter(None, cancel_order_timestamps), default=0)):
        order = {
            'order_type': order_type,
            'pair': selected_pair,
            'price': order_price if order_type in ['BUY_LIMIT', 'SELL_LIMIT'] else current_price,
            'quantity': order_quantity,
            'total': order_total_cost,
            'order_creation_date': datetime.now(),
            'order_complete_date': None,
            'status': 'Pending' if order_type in ['BUY_LIMIT', 'SELL_LIMIT'] else 'Filled'
        }
        
        # If it's MARKET order immediately fill
        if order['status'] == 'Filled':
            order['order_complete_date'] = datetime.now()
            if order_type == 'MARKET_BUY':
                crypto_currency = selected_pair[:3]
                fake_balances[crypto_currency] += order['quantity']
                fake_balances['USDT'] -= order['total']
            elif order_type == 'MARKET_SELL':
                crypto_currency = selected_pair[:3]
                fake_balances[crypto_currency] -= order['quantity']
                fake_balances['USDT'] += order['total']
        orders.append(order)

    # Order cancellation
    if ctx.triggered and 'cancel-button' in ctx.triggered[0]['prop_id']:
        cancel_index = json.loads(ctx.triggered[0]['prop_id'].split('.')[0])['index']
        if orders[cancel_index]['status'] == 'Pending':
            orders[cancel_index]['status'] = 'Cancelled'

    # Check for filled orders and generate notifications
    notifications = check_limit_orders(prices)

    fig = go.Figure()
    for pair in pairs:
        fig.add_trace(go.Scatter(x=timestamps[pair], y=prices[pair], mode='lines', name=pair))

    fig.update_layout(title=f'Live Crypto Prices ({selected_time_frame})', xaxis_title='Time', yaxis_title='Price')

    update_interval = time_frame_to_interval[selected_time_frame]

    # Order History Table
    order_history_table = html.Table([
        html.Thead(html.Tr([html.Th("Type"), html.Th("Pair"), html.Th("Price"), html.Th("Quantity"), html.Th("Total"), html.Th("Status"), html.Th("Creation Date"), html.Th("Completion Date"), html.Th("Action")])),
        html.Tbody([
            html.Tr([html.Td(order['order_type']), html.Td(order['pair']), html.Td(order['price']), html.Td(order['quantity']), html.Td(order['total']),
                     html.Td(order['status']), html.Td(order['order_creation_date']), html.Td(order['order_complete_date']),
                     html.Td(html.Button('Cancel', id={'type': 'cancel-button', 'index': i}, disabled=(order['status'] != 'Pending')))])
            for i, order in enumerate(orders)
        ])
    ])

    # Update the balance outputs
    balance_output = f"Balance: {fake_balances['USDT']:.2f} USDT"
    btc_balance_output = f"BTC Balance: {fake_balances['BTC']:.6f} BTC"
    eth_balance_output = f"ETH Balance: {fake_balances['ETH']:.6f} ETH"
    ltc_balance_output = f"LTC Balance: {fake_balances['LTC']:.6f} LTC"
    xrp_balance_output = f"XRP Balance: {fake_balances['XRP']:.2f} XRP"

    # Return all updates
    return fig, update_interval, order_history_table, html.Ul([html.Li(notification) for notification in notifications]), button_disabled, balance_output, btc_balance_output, eth_balance_output, ltc_balance_output, xrp_balance_output

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run_server(debug=True, host='0.0.0.0', port=port)
