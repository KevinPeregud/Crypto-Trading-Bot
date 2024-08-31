import ccxt
import time
import numpy as np

# Replace with your own API keys
API_KEY = 'your_api_key'
API_SECRET = 'your_api_secret'

# Initialize the exchange (e.g., Binance)
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
})

# Trading pair and time interval
symbol = 'BTC/USDT'
timeframe = '5m'
sma_period = 14
rsi_period = 14
macd_fast_period = 12
macd_slow_period = 26
macd_signal_period = 9

# Define thresholds for RSI
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Define risk management parameters
RISK_PER_TRADE = 0.01  # 1% of account balance
STOP_LOSS_PERCENT = 0.02  # 2% below entry price
PROFIT_TARGET_PERCENT = 0.05  # 5% above entry price

# Retrieve account balance
def get_account_balance():
    balance = exchange.fetch_balance()
    return balance['total']['USDT']

# Calculate position size based on risk
def calculate_position_size(account_balance, entry_price, stop_loss_price):
    risk_amount = account_balance * RISK_PER_TRADE
    position_size = risk_amount / abs(entry_price - stop_loss_price)
    return position_size

# Fetch OHLCV data
def fetch_ohlcv(symbol, timeframe):
    return exchange.fetch_ohlcv(symbol, timeframe)

# Calculate the Simple Moving Average (SMA)
def calculate_sma(data, period):
    closes = [x[4] for x in data]
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period

# Calculate the Relative Strength Index (RSI)
def calculate_rsi(data, period):
    closes = np.array([x[4] for x in data])
    deltas = np.diff(closes)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    if down == 0:
        return 100
    rs = up / down
    rsi = 100. - 100. / (1. + rs)

    for i in range(period, len(closes)):
        delta = deltas[i - 1]
        if delta > 0:
            up_val = delta
            down_val = 0.
        else:
            up_val = 0.
            down_val = -delta

        up = (up * (period - 1) + up_val) / period
        down = (down * (period - 1) + down_val) / period

        if down == 0:
            rs = float('inf')
            rsi = 100
        else:
            rs = up / down
            rsi = 100. - 100. / (1. + rs)

    return rsi

# Calculate the MACD and Signal Line
def calculate_macd(data, fast_period, slow_period, signal_period):
    closes = np.array([x[4] for x in data])
    ema_fast = calculate_ema(closes, fast_period)
    ema_slow = calculate_ema(closes, slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal_period)
    return macd_line[-1], signal_line[-1]

# Calculate Exponential Moving Average (EMA)
def calculate_ema(prices, period):
    ema = []
    k = 2 / (period + 1)
    for i, price in enumerate(prices):
        if i == 0:
            ema.append(price)
        else:
            ema.append(price * k + ema[-1] * (1 - k))
    return np.array(ema)

# Place a market order
def place_order(symbol, side, amount, stop_loss_price=None, take_profit_price=None):
    try:
        order = exchange.create_market_order(symbol, side, amount)
        print(f"Order placed: {order}")

        if stop_loss_price or take_profit_price:
            manage_risk(symbol, side, amount, stop_loss_price, take_profit_price)

        return order
    except Exception as e:
        print(f"Failed to place {side} order: {e}")

# Manage risk by setting stop-loss and take-profit
def manage_risk(symbol, side, amount, stop_loss_price, take_profit_price):
    try:
        if stop_loss_price:
            stop_loss_order = exchange.create_order(symbol, 'stop_market', 'sell', amount, stop_loss_price)
            print(f"Stop-loss order placed: {stop_loss_order}")

        if take_profit_price:
            take_profit_order = exchange.create_order(symbol, 'limit', 'sell', amount, take_profit_price)
            print(f"Take-profit order placed: {take_profit_order}")

    except Exception as e:
        print(f"Failed to manage risk: {e}")

# Retrieve the last order for the given symbol
def get_last_order(symbol):
    try:
        orders = exchange.fetch_closed_orders(symbol, limit=1)
        if orders:
            return orders[0]
        return None
    except Exception as e:
        print(f"Failed to fetch last order: {e}")
        return None

def main():
    print("Starting combined strategy trading bot with risk management...")
    while True:
        try:
            ohlcv = fetch_ohlcv(symbol, timeframe)
            if len(ohlcv) < max(sma_period, rsi_period, macd_slow_period + macd_signal_period):
                print("Not enough data to calculate indicators.")
                time.sleep(60)
                continue

            sma = calculate_sma(ohlcv, sma_period)
            rsi = calculate_rsi(ohlcv, rsi_period)
            macd_line, signal_line = calculate_macd(ohlcv, macd_fast_period, macd_slow_period, macd_signal_period)
            last_close = ohlcv[-1][4]

            print(f"Last Close: {last_close}, SMA: {sma:.2f}, RSI: {rsi:.2f}, MACD: {macd_line:.5f}, Signal: {signal_line:.5f}")

            # Determine Buy/Sell Signals
            buy_signal = False
            sell_signal = False

            # SMA Condition
            if last_close > sma:
                sma_condition = 'bullish'
            else:
                sma_condition = 'bearish'

            # RSI Condition
            if rsi < RSI_OVERSOLD:
                rsi_condition = 'oversold'
            elif rsi > RSI_OVERBOUGHT:
                rsi_condition = 'overbought'
            else:
                rsi_condition = 'neutral'

            # MACD Condition
            if macd_line > signal_line:
                macd_condition = 'bullish'
            elif macd_line < signal_line:
                macd_condition = 'bearish'
            else:
                macd_condition = 'neutral'

            # Combine Conditions for Buy
            if (sma_condition == 'bullish') and (rsi_condition == 'oversold') and (macd_condition == 'bullish'):
                buy_signal = True

            # Combine Conditions for Sell
            if (sma_condition == 'bearish') and (rsi_condition == 'overbought') and (macd_condition == 'bearish'):
                sell_signal = True

            # Retrieve the last order to prevent duplicate actions
            last_order = get_last_order(symbol)
            last_order_side = last_order['side'] if last_order else None

            # Execute Buy Signal
            if buy_signal and last_order_side != 'buy':
                print("All indicators align for BUY signal.")
                account_balance = get_account_balance()
                stop_loss_price = last_close * (1 - STOP_LOSS_PERCENT)
                take_profit_price = last_close * (1 + PROFIT_TARGET_PERCENT)
                position_size = calculate_position_size(account_balance, last_close, stop_loss_price)
                place_order(symbol, 'buy', position_size, stop_loss_price, take_profit_price)

            # Execute Sell Signal
            elif sell_signal and last_order_side != 'sell':
                print("All indicators align for SELL signal.")
                account_balance = get_account_balance()
                stop_loss_price = last_close * (1 + STOP_LOSS_PERCENT)
                take_profit_price = last_close * (1 - PROFIT_TARGET_PERCENT)
                position_size = calculate_position_size(account_balance, last_close, stop_loss_price)
                place_order(symbol, 'sell', position_size, stop_loss_price, take_profit_price)

            else:
                print("No trading signal or duplicate signal detected.")

            time.sleep(60)  # Wait before next check

        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    main()
