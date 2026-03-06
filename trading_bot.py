import discord
import os
from discord.ext import commands, tasks
import pandas_ta as ta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta


TOKEN = os.getenv('TOKEN')
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
MY_ID = 969116847055011850

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

SYMBOL = "AAPL"
CHANNEL_ID = None


# --- 2. ฟังก์ชันวิเคราะห์หุ้น (RSI + EMA 200) ---
def get_advanced_signal(symbol):
    try:
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Hour,
            start=datetime.now() - timedelta(days=20)
        )
        # บรรทัดที่เคยมีปัญหา แก้เป็น .df ให้แล้วครับ
        bars = data_client.get_stock_bars(request_params).df

        bars['RSI'] = ta.rsi(bars['close'], length=14)
        bars['EMA_200'] = ta.ema(bars['close'], length=200)

        last_row = bars.iloc[-1]
        price = last_row['close']
        rsi = last_row['RSI']
        ema = last_row['EMA_200']

        # กลยุทธ์: ซื้อเมื่อราคาถูก (RSI ต่ำ) และเป็นขาขึ้น (เหนือ EMA 200)
        if rsi < 35 and price > ema:
            return price, rsi, "BUY"
        elif rsi > 65:
            return price, rsi, "SELL"

        return price, rsi, "HOLD"
    except Exception as e:
        print(f"Error: {e}")
        return None, None, "ERROR"


# --- 3. ระบบทำงานอัตโนมัติ ---
@tasks.loop(minutes=30)
async def trade_loop():
    global CHANNEL_ID
    if not CHANNEL_ID: return
    channel = bot.get_channel(CHANNEL_ID)

    price, rsi, signal = get_advanced_signal(SYMBOL)

    if signal == "BUY":
        order = MarketOrderRequest(symbol=SYMBOL, qty=1, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
        trading_client.submit_order(order)
        # บรรทัดที่ 72 แก้ให้ปิดเครื่องหมายครบแล้วครับ
        await channel.send(f"✅ **ซื้อหุ้น!** {SYMBOL} @ ${price:.2f} (RSI: {rsi:.2f})")
    elif signal == "SELL":
        try:
            trading_client.close_position(SYMBOL)
            await channel.send(f"💰 **ขายหุ้น!** {SYMBOL} @ ${price:.2f} (RSI: {rsi:.2f})")
        except:
            pass


# --- 4. คำสั่ง Discord ---
@bot.command()
async def start(ctx):
    if ctx.author.id != MY_ID: return
    global CHANNEL_ID
    CHANNEL_ID = ctx.channel.id
    if not trade_loop.is_running(): trade_loop.start()
    await ctx.send(f"🤖 **TRF Bot เริ่มรันระบบวิเคราะห์ {SYMBOL} แล้ว!**")


@bot.command()
async def status(ctx):
    if ctx.author.id != MY_ID: return
    try:
        acc = trading_client.get_account()
        await ctx.send(
            f"📊 **พอร์ตของ Atom**\n💵 เงินสด: ${float(acc.cash):,.2f}\n📈 รวม: ${float(acc.portfolio_value):,.2f}")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')


bot.run(TOKEN)