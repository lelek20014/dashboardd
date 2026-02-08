import os
import time
import logging
import json
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, AssetStatus, AssetClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============== CONFIGURATION ===============
def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except:
        return {
            "symbols": ["AAPL", "TSLA", "NVDA", "AMZN", "META", "GOOGL", "MCD", "HOOD"],
            "buy_drop_percent": 1.0,
            "sell_rise_percent": 2.0,
            "stake_settings": {"mode": "fixed", "fixed_amount": 10.0, "percent_amount": 1.0},
            "currency": "USD",
            "check_interval": 60,
            "profit_mode": "TAKE",
            "always_on": True,
            "always_on_amount": 1.0
        }

CONFIG = load_config()
CONFIG["dry_run"] = os.getenv("TRADING_MODE", "DRY") == "DRY"

class ActiveLotsManager:
    def __init__(self, filename="lots.json"):
        self.filename = filename
        self.lots = self._load_lots()

    def _load_lots(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading lots: {e}")
        return {}

    def _save_lots(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.lots, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving lots: {e}")

    def add_lot(self, symbol, buy_price, quantity):
        if symbol not in self.lots:
            self.lots[symbol] = []
        self.lots[symbol].append({
            'buy_price': buy_price,
            'quantity': quantity,
            'timestamp': time.time()
        })
        self._save_lots()
        logger.info(f"SUCCESS: Added lot for {symbol}: {quantity:.6f} shares @ {buy_price:.2f}")

    def remove_lot(self, symbol, lot_index):
        if symbol in self.lots and 0 <= lot_index < len(self.lots[symbol]):
            lot = self.lots[symbol].pop(lot_index)
            if not self.lots[symbol]:
                del self.lots[symbol]
            self._save_lots()
            logger.info(f"SUCCESS: Removed lot for {symbol}: {lot['quantity']:.6f} shares @ {lot['buy_price']:.2f}")
            return True
        return False

    def get_lots(self, symbol):
        return self.lots.get(symbol, [])

    def get_lowest_buy_price(self, symbol):
        lots = self.get_lots(symbol)
        if not lots:
            return None
        return min(lot['buy_price'] for lot in lots)

class AlpacaAPI:
    def __init__(self):
        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_API_SECRET")
        paper = os.getenv("TRADING_MODE", "PAPER") == "PAPER"
        
        self.trading_client = TradingClient(api_key, api_secret, paper=paper)
        self.data_client = StockHistoricalDataClient(api_key, api_secret)
        self.asset_info = {}

    def is_market_open(self):
        """
        Checks if the market is currently open.
        """
        try:
            clock = self.trading_client.get_clock()
            return clock.is_open
        except Exception as e:
            logger.error(f"Error checking market clock: {e}")
            return False

    def cancel_all_orders(self):
        """
        Cancels all open orders on Alpaca.
        """
        try:
            return self.trading_client.cancel_orders()
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return None

    def close_all_positions(self):
        """
        Closes all open positions on Alpaca.
        """
        try:
            # cancel_orders=True ensures pending orders are also cancelled
            return self.trading_client.close_all_positions(cancel_orders=True)
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
            return None

    def get_tradeable_assets(self):
        """
        Fetches all tradeable and fractional assets from Alpaca.
        """
        try:
            # We filter for active, tradeable US equities that support fractional shares
            from alpaca.trading.requests import GetAssetsRequest
            request_params = GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY)
            assets = self.trading_client.get_all_assets(request_params)
            return [a.symbol for a in assets if a.tradable and a.fractionable]
        except Exception as e:
            logger.error(f"Error fetching tradeable assets: {e}")
            return []

    def get_multiple_prices(self, symbols):
        """
        Fetches latest quotes for multiple symbols in one go.
        """
        if not symbols:
            return {}
        try:
            request_params = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = self.data_client.get_stock_latest_quote(request_params)
            return {s: float(q.ask_price if q.ask_price else 0) for s, q in quotes.items()}
        except Exception as e:
            logger.error(f"Error fetching multiple prices: {e}")
            return {}

    def get_account_equity(self):
        """
        Fetches the total account equity.
        """
        try:
            account = self.trading_client.get_account()
            return float(account.equity)
        except Exception as e:
            logger.error(f"Error fetching account equity: {e}")
            return None

    def get_account_cash(self):
        """
        Fetches the account cash balance.
        """
        try:
            account = self.trading_client.get_account()
            return float(account.cash)
        except Exception as e:
            logger.error(f"Error fetching account cash: {e}")
            return None

    def get_asset_info(self, symbol):
        if symbol in self.asset_info:
            return self.asset_info[symbol]
        try:
            asset = self.trading_client.get_asset(symbol)
            self.asset_info[symbol] = asset
            return asset
        except Exception as e:
            logger.error(f"Error fetching asset info for {symbol}: {e}")
        return None

    def get_current_price(self, symbol):
        """
        Fetches the current price of a symbol from Alpaca.
        """
        try:
            request_params = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            latest_quote = self.data_client.get_stock_latest_quote(request_params)
            # Use bid/ask mid or just one side. Alpaca latest quote has 'ask_price' and 'bid_price'
            price = latest_quote[symbol].ask_price
            if not price:
                # Fallback to last trade if quote is not available (e.g. after hours)
                from alpaca.data.requests import StockLatestTradeRequest
                latest_trade = self.data_client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
                price = latest_trade[symbol].price
            return float(price)
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def get_last_execution(self, symbol, order_id):
        """
        Fetches the execution details for a specific order.
        """
        try:
            # Wait a moment for execution to be recorded
            time.sleep(1)
            order = self.trading_client.get_order_by_id(order_id)
            if order.status == OrderStatus.FILLED:
                return float(order.filled_qty), float(order.filled_avg_price)
            elif order.status == OrderStatus.PARTIALLY_FILLED:
                 return float(order.filled_qty), float(order.filled_avg_price)
        except Exception as e:
            logger.error(f"Error fetching execution for {symbol} {order_id}: {e}")
        return None, None

    def place_order(self, symbol, side, quantity, dry_run=True):
        """
        Places a market order on Alpaca.
        """
        if dry_run:
            logger.info(f"[DRY RUN] {side.upper()} order for {quantity:.6f} {symbol}")
            return {"id": "DRY_RUN_ID"}

        try:
            # Alpaca Market orders use 'qty' (shares) or 'notional' (dollars)
            # If side is Buy, we often use notional if we want to spend fixed USD.
            # If side is Sell, we use qty.
            
            order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
            
            if order_side == OrderSide.BUY:
                # quantity is USD amount
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    notional=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY
                )
            else:
                # quantity is share amount
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY
                )
            
            order = self.trading_client.submit_order(order_data=order_data)
            return {"id": order.id}
        except Exception as e:
            logger.error(f"Error placing {side} order for {symbol}: {e}")
            return None

def check_grid_triggers(symbol, current_price, manager, config):
    actions = []
    lots = manager.get_lots(symbol)
    
    # Check for SELL triggers
    for i, lot in enumerate(lots):
        buy_price = lot['buy_price']
        profit_pct = (current_price - buy_price) / buy_price * 100.0
        if profit_pct >= config['sell_rise_percent']:
            actions.append(('SELL', i, current_price))
            
    # Check for BUY triggers
    lowest_buy = manager.get_lowest_buy_price(symbol)
    if not lots:
        # No lots - buy initial position
        amount = config.get('always_on_amount', 1.0) if config.get('always_on', True) else config.get('trade_amount', 10.0)
        actions.append(('BUY', current_price, amount))
    else:
        drop_pct = (lowest_buy - current_price) / lowest_buy * 100.0
        if drop_pct >= config['buy_drop_percent']:
            actions.append(('BUY', current_price, config['trade_amount']))
            
    return actions

class TradingBot:
    def __init__(self, config):
        self.config = config
        self.manager = ActiveLotsManager()
        self.api = AlpacaAPI()
        
    def execute_buy(self, symbol, amount, price):
        # amount is in USD (notional)
        order = self.api.place_order(symbol, 'buy', amount, dry_run=self.config['dry_run'])
        if order:
            if not self.config['dry_run']:
                order_id = order.get('id')
                actual_qty, actual_price = self.api.get_last_execution(symbol, order_id)
                if actual_qty and actual_price:
                    logger.info(f"REAL BUY: Executed {actual_qty:.6f} {symbol} @ {actual_price:.4f}")
                    self.manager.add_lot(symbol, actual_price, actual_qty)
                    return True
                else:
                    logger.info(f"REAL BUY: Order {order_id} is pending/queued (Market may be closed). Using approximations for tracking.")
            
            # Fallback for dry run or if execution fetch failed (pending order)
            actual_quantity = amount / price # Approximate quantity bought
            self.manager.add_lot(symbol, price, actual_quantity)
            return True
        return False

    def execute_sell(self, symbol, lot_index, price):
        lots = self.manager.get_lots(symbol)
        if not (0 <= lot_index < len(lots)):
            return False

        lot = lots[lot_index]
        buy_price = lot['buy_price']
        quantity = lot['quantity']
        
        cost_basis = buy_price * quantity
        current_value = price * quantity
        profit = current_value - cost_basis

        if self.config['profit_mode'] == 'LEAVE':
            # Sell only the cost basis worth of shares
            sell_quantity = cost_basis / price
            sell_quantity = min(sell_quantity, quantity)
            logger.info(f"PROFIT MODE LEAVE: Selling cost basis, leaving profit in shares.")
        else: # 'TAKE'
            sell_quantity = quantity
            logger.info(f"PROFIT MODE TAKE: Selling entire lot. Profit: {profit:.2f} {self.config['currency']}")

        # Alpaca uses 'qty' for shares in sell orders
        order = self.api.place_order(symbol, 'sell', sell_quantity, dry_run=self.config['dry_run'])
        if order:
            if not self.config['dry_run']:
                order_id = order.get('id')
                actual_qty, actual_price = self.api.get_last_execution(symbol, order_id)
                if actual_qty and actual_price:
                    logger.info(f"REAL SELL: Executed {actual_qty:.6f} {symbol} @ {actual_price:.4f}")
                else:
                    logger.info(f"REAL SELL: Order {order_id} is pending/queued (Market may be closed).")
            
            self.manager.remove_lot(symbol, lot_index)
            return True
        return False

    def run(self):
        logger.info("="*60)
        logger.info("ALPACA DIP BUYING GRID BOT STARTED")
        logger.info("="*60)

        try:
            while True:
                # Reload configuration
                self.config = load_config()
                self.config["dry_run"] = os.getenv("TRADING_MODE", "DRY") == "DRY"
                
                market_open = self.api.is_market_open()
                
                # Calculate dynamic stake
                stake_settings = self.config.get("stake_settings", {})
                if stake_settings.get("mode") == "percent":
                    equity = self.api.get_account_equity()
                    if equity:
                        trade_amount = equity * (stake_settings.get("percent_amount", 1.0) / 100.0)
                        logger.info(f"Dynamic Stake: {stake_settings['percent_amount']}% of ${equity:.2f} = ${trade_amount:.2f}")
                    else:
                        trade_amount = stake_settings.get("fixed_amount", 10.0)
                        logger.warning(f"Could not fetch equity. Falling back to fixed stake: ${trade_amount:.2f}")
                else:
                    trade_amount = stake_settings.get("fixed_amount", 10.0)
                
                # Update config with current loop's trade_amount
                self.config['trade_amount'] = trade_amount

                symbols = self.config['symbols']
                
                # Fetch all prices in batches for efficiency
                all_prices = {}
                batch_size = 200
                for i in range(0, len(symbols), batch_size):
                    batch = symbols[i:i + batch_size]
                    all_prices.update(self.api.get_multiple_prices(batch))
                    
                for symbol in symbols:
                    current_price = all_prices.get(symbol)
                    if current_price is None:
                        # Fallback for individual price if batch failed or missing
                        current_price = self.api.get_current_price(symbol)
                    
                    if current_price is None:
                        continue
                    
                    lowest_buy = self.manager.get_lowest_buy_price(symbol)
                    num_lots = len(self.manager.get_lots(symbol))
                    
                    status_msg = f"{symbol:8}: {current_price:8.4f} {self.config['currency']}"
                    if lowest_buy:
                        drop = (lowest_buy - current_price) / lowest_buy * 100
                        status_msg += f" | Lowest Buy: {lowest_buy:8.4f} ({drop:6.2f}% drop) | Lots: {num_lots}"
                    else:
                        status_msg += " | No active lots"
                    
                    logger.info(status_msg)
                    
                    # Execute actions (Alpaca will queue orders if market is closed)
                    actions = check_grid_triggers(symbol, current_price, self.manager, self.config)
                    
                    # Sort sells to avoid index shifting issues (though we pop anyway)
                    sells = sorted([a for a in actions if a[0] == 'SELL'], key=lambda x: x[1], reverse=True)
                    buys = [a for a in actions if a[0] == 'BUY']
                    
                    for _, lot_index, price in sells:
                        self.execute_sell(symbol, lot_index, price)
                    
                    for _, price, amount in buys:
                        self.execute_buy(symbol, amount, price)
                                        
                time.sleep(self.config['check_interval'])
        except KeyboardInterrupt:
            logger.info("Bot stopping...")
        except Exception as e:
            logger.error(f"UNEXPECTED ERROR: {e}")
        finally:
            logger.info("Bot shutdown complete.")

if __name__ == "__main__":
    bot = TradingBot(CONFIG)
    bot.run()
