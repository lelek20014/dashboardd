import os
import json
from flask import Flask, render_template_string, redirect, url_for, request, flash, jsonify
from bot import ActiveLotsManager, AlpacaAPI

app = Flask(__name__)
app.secret_key = os.urandom(24)

api = AlpacaAPI()

def load_full_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except:
        return {}

def save_full_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pasiu Bot | Terminal</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-dark: #050505;
            --card-bg: #111111;
            --accent: #00d2ff;
            --accent-gold: #ffc107;
            --text-main: #ffffff;
            --text-muted: #e0e0e0;
            --border-color: #222222;
            --danger: #ff4b2b;
            --success: #00ff88;
        }
        body { 
            background-color: var(--bg-dark); 
            color: var(--text-main);
            font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
            padding-bottom: 50px;
        }
        .navbar { background-color: #000; border-bottom: 1px solid var(--border-color); margin-bottom: 20px; }
        .stats-card {
            background: linear-gradient(145deg, #151515, #0a0a0a);
            border: 1px solid var(--border-color);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
        }
        .stats-label { color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
        .stats-value { font-size: 1.5rem; font-weight: 800; color: #ffffff; }
        .stats-delta { font-size: 0.85rem; font-weight: 600; }
        
        .card { 
            background-color: var(--card-bg); 
            border: 1px solid var(--border-color); 
            border-radius: 12px;
            margin-bottom: 24px;
        }
        .card-header { 
            background-color: rgba(255,255,255,0.02); 
            border-bottom: 1px solid var(--border-color);
            font-weight: 700;
            font-size: 0.85rem;
            color: var(--accent);
            padding: 15px 20px;
        }
        
        .lot-item { 
            background: rgba(255,255,255,0.02);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 12px;
            border-left: 4px solid var(--accent);
        }
        .progress { background-color: #222; height: 6px; margin-top: 10px; border-radius: 3px; }
        .progress-bar { background: linear-gradient(90deg, var(--accent), var(--success)); }

        .symbol-badge {
            background-color: #1a1a1a;
            border: 1px solid #333;
            padding: 5px 12px;
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            margin: 0 5px 5px 0;
            font-size: 0.8rem;
        }
        .form-control, .form-select {
            background-color: #151515;
            border: 1px solid #333;
            color: white;
        }
        .form-control:focus, .form-select:focus {
            background-color: #151515;
            border-color: var(--accent);
            color: white;
            box-shadow: 0 0 0 0.25rem rgba(0, 210, 255, 0.1);
        }
        .highlight-value { color: #ffffff; text-shadow: 0 0 5px rgba(255,255,255,0.1); }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark">
        <div class="container">
            <span class="navbar-brand mb-0 h1"><i class="fas fa-terminal me-2 text-accent"></i>PASIU BOT <span class="text-muted fs-6 fw-normal ms-2">PORTFOLIO TERMINAL</span></span>
            <div class="d-flex align-items-center">
                 <span class="badge {{ 'bg-success' if market_open else 'bg-secondary' }} me-3 px-3 py-2">
                    <i class="fas fa-clock me-1"></i> Market: {{ "OPEN" if market_open else "CLOSED" }}
                 </span>
                 <div class="text-end">
                    <div class="text-muted small">Trading Mode</div>
                    <div class="text-white fw-bold small">{{ trading_mode }}</div>
                 </div>
            </div>
        </div>
    </nav>

    <div class="container">
        <!-- Portfolio Pulse -->
        <div class="row mb-4">
            <div class="col-md-2">
                <div class="stats-card">
                    <div class="stats-label">Account Equity</div>
                    <div class="stats-value highlight-value" id="account-equity">$0.00</div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="stats-card">
                    <div class="stats-label">Cash Balance</div>
                    <div class="stats-value highlight-value" id="cash-balance">$0.00</div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="stats-card">
                    <div class="stats-label">Total Invested</div>
                    <div class="stats-value highlight-value" id="total-basis">$0.00</div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="stats-card">
                    <div class="stats-label">Market Value</div>
                    <div class="stats-value highlight-value" id="market-value">$0.00</div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="stats-card">
                    <div class="stats-label">Unrealized P/L</div>
                    <div class="stats-value stats-delta" id="total-pl">$0.00</div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="stats-card">
                    <div class="stats-label">Active Symbols</div>
                    <div class="stats-value highlight-value" id="active-count">0</div>
                </div>
            </div>
        </div>

        <div class="row">
            <!-- Left: Chart & Focus -->
            <div class="col-lg-4">
                <div class="card">
                    <div class="card-header"><i class="fas fa-pie-chart me-2"></i>Asset Allocation</div>
                    <div class="card-body">
                        <canvas id="allocationChart" height="250"></canvas>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span><i class="fas fa-crosshairs me-2"></i>Focus List</span>
                        <form action="{{ url_for('add_all_symbols') }}" method="post" style="display:inline">
                            <button type="submit" class="btn btn-link btn-sm p-0 text-accent text-decoration-none">Add All</button>
                        </form>
                    </div>
                    <div class="card-body">
                        <div id="symbol-list" style="max-height: 150px; overflow-y: auto;" class="mb-3">
                            {% for sym in config.symbols %}
                                <span class="symbol-badge">
                                    {{ sym }}
                                    <form action="{{ url_for('remove_symbol') }}" method="post" style="display:inline">
                                        <input type="hidden" name="symbol" value="{{ sym }}">
                                        <button type="submit" class="bg-transparent border-0 ms-1 p-0 text-danger small"><i class="fas fa-times"></i></button>
                                    </form>
                                </span>
                            {% endfor %}
                        </div>
                        <form action="{{ url_for('add_symbol') }}" method="post" class="input-group input-group-sm">
                            <input type="text" name="symbol" class="form-control" placeholder="Add Ticker...">
                            <button type="submit" class="btn btn-accent">ADD</button>
                        </form>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header"><i class="fas fa-cog me-2"></i>Global Strategy</div>
                    <div class="card-body">
                        <form action="{{ url_for('update_stake') }}" method="post">
                            <div class="mb-2">
                                <label class="stats-label">Stake Mode</label>
                                <select name="mode" class="form-select form-select-sm">
                                    <option value="fixed" {{ 'selected' if config.stake_settings.mode == 'fixed' }}>Fixed Amount</option>
                                    <option value="percent" {{ 'selected' if config.stake_settings.mode == 'percent' }}>% Equity</option>
                                </select>
                            </div>
                            <div class="row g-2 mb-3">
                                <div class="col-6">
                                    <label class="stats-label">Fixed ($)</label>
                                    <input type="number" step="0.01" name="fixed_amount" class="form-control form-control-sm" value="{{ config.stake_settings.fixed_amount }}">
                                </div>
                                <div class="col-6">
                                    <label class="stats-label">Equity (%)</label>
                                    <input type="number" step="0.1" name="percent_amount" class="form-control form-control-sm" value="{{ config.stake_settings.percent_amount }}">
                                </div>
                            </div>
                            <button type="submit" class="btn btn-outline-light btn-sm w-100">Update Capital Logic</button>
                        </form>
                    </div>
                </div>
            </div>

            <!-- Right: Live Monitor -->
            <div class="col-lg-8">
                <div class="card">
                    <div class="card-header d-flex justify-content-between">
                        <span><i class="fas fa-wave-square me-2"></i>Execution Monitor</span>
                        <span class="text-muted small">Auto-refresh active</span>
                    </div>
                    <div class="card-body" id="lots-container">
                        <div class="text-center py-5">
                            <div class="spinner-border text-accent" role="status"></div>
                            <p class="mt-3 text-muted">Syncing with Alpaca Network...</p>
                        </div>
                    </div>
                </div>
                
                <div class="row g-3">
                    <div class="col-6">
                        <form action="{{ url_for('cancel_orders') }}" method="post">
                            <button type="submit" class="btn btn-outline-warning w-100 fw-bold py-3"><i class="fas fa-ban me-2"></i>CANCEL QUEUE</button>
                        </form>
                    </div>
                    <div class="col-6">
                        <form action="{{ url_for('close_positions') }}" method="post">
                            <button type="submit" class="btn btn-outline-danger w-100 fw-bold py-3"><i class="fas fa-skull-crossbones me-2"></i>LIQUIDATE ALL</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let allocationChart = null;

        async function updateDashboard() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                // Update Portfolio Pulse
                document.getElementById('account-equity').innerText = '$' + data.equity.toFixed(2);
                document.getElementById('cash-balance').innerText = '$' + data.cash.toFixed(2);
                document.getElementById('total-basis').innerText = '$' + data.total_basis.toFixed(2);
                document.getElementById('market-value').innerText = '$' + data.market_value.toFixed(2);
                
                const plElement = document.getElementById('total-pl');
                const pl = data.market_value - data.total_basis;
                const plPercent = data.total_basis > 0 ? (pl / data.total_basis * 100) : 0;
                plElement.innerText = (pl >= 0 ? '+' : '') + '$' + pl.toFixed(2) + ' (' + plPercent.toFixed(2) + '%)';
                plElement.style.color = pl >= 0 ? 'var(--success)' : 'var(--danger)';
                
                document.getElementById('active-count').innerText = Object.keys(data.lots).length;

                // Update Chart
                const chartLabels = Object.keys(data.allocation);
                const chartData = Object.values(data.allocation);
                
                if (!allocationChart) {
                    const ctx = document.getElementById('allocationChart').getContext('2d');
                    allocationChart = new Chart(ctx, {
                        type: 'doughnut',
                        data: {
                            labels: chartLabels,
                            datasets: [{
                                data: chartData,
                                backgroundColor: ['#00d2ff', '#3a7bd5', '#00ff88', '#ffc107', '#ff4b2b', '#9d50bb', '#6e48aa'],
                                borderWidth: 0
                            }]
                        },
                        options: {
                            plugins: { legend: { display: false } },
                            cutout: '70%'
                        }
                    });
                } else {
                    allocationChart.data.labels = chartLabels;
                    allocationChart.data.datasets[0].data = chartData;
                    allocationChart.update();
                }

                // Update Lots Container
                const container = document.getElementById('lots-container');
                if (Object.keys(data.lots).length === 0) {
                    container.innerHTML = '<div class="text-center py-5 text-muted">No active positions tracked</div>';
                } else {
                    let html = '';
                    for (const [symbol, lots] of Object.entries(data.lots)) {
                        const currentPrice = data.prices[symbol] || 0;
                        html += `<div class="mb-4">
                                    <div class="d-flex justify-content-between align-items-end mb-2">
                                        <h6 class="m-0"><span class="badge bg-primary me-2">${symbol}</span> <span class="text-white">$${currentPrice.toFixed(2)}</span></h6>
                                    </div>`;
                        
                        lots.forEach(lot => {
                            const profitPct = ((currentPrice - lot.buy_price) / lot.buy_price * 100);
                            const targetPct = 2.0; // Hardcoded sell target for UI ref
                            const progress = Math.min(Math.max((profitPct / targetPct) * 100, 0), 100);
                            
                            html += `<div class="lot-item">
                                        <div class="d-flex justify-content-between align-items-center mb-1">
                                            <div>
                                                <div class="small text-muted">Shares</div>
                                                <div class="fw-bold highlight-value">${lot.quantity.toFixed(6)}</div>
                                            </div>
                                            <div>
                                                <div class="small text-muted">Basis</div>
                                                <div class="fw-bold highlight-value">$${(lot.quantity * lot.buy_price).toFixed(2)}</div>
                                            </div>
                                            <div class="text-end">
                                                <div class="small text-muted">Return</div>
                                                <div class="fw-bold" style="color: ${profitPct >= 0 ? 'var(--success)' : 'var(--danger)'}">
                                                    ${profitPct >= 0 ? '+' : ''}${profitPct.toFixed(2)}%
                                                </div>
                                            </div>
                                        </div>
                                        <div class="progress">
                                            <div class="progress-bar" role="progressbar" style="width: ${progress}%"></div>
                                        </div>
                                        <div class="d-flex justify-content-between mt-1">
                                            <span style="font-size: 0.65rem" class="text-muted">PURCHASE</span>
                                            <span style="font-size: 0.65rem" class="text-muted">TAKE PROFIT (2%)</span>
                                        </div>
                                    </div>`;
                        });
                        html += `</div>`;
                    }
                    container.innerHTML = html;
                }

            } catch (e) {
                console.error("Dashboard Update Failed:", e);
            }
        }

        // Start updates
        updateDashboard();
        setInterval(updateDashboard, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    config = load_full_config()
    market_open = api.is_market_open()
    trading_mode = os.getenv("TRADING_MODE", "DRY")
    return render_template_string(HTML_TEMPLATE, config=config, market_open=market_open, trading_mode=trading_mode)

@app.route('/api/data')
def get_data():
    manager = ActiveLotsManager()
    lots = manager.lots
    symbols = list(lots.keys())
    
    # Batch fetch prices
    prices = api.get_multiple_prices(symbols)
    
    # Get account balance and equity
    equity = api.get_account_equity() or 0
    cash = api.get_account_cash() or 0
    
    total_basis = 0
    market_value = 0
    allocation = {}
    
    for symbol, lot_list in lots.items():
        sym_basis = 0
        current_p = prices.get(symbol, 0)
        
        for lot in lot_list:
            b = lot['quantity'] * lot['buy_price']
            total_basis += b
            sym_basis += b
            market_value += lot['quantity'] * current_p
            
        allocation[symbol] = sym_basis

    return jsonify({
        "lots": lots,
        "prices": prices,
        "total_basis": total_basis,
        "market_value": market_value,
        "equity": equity,
        "cash": cash,
        "allocation": allocation
    })

@app.route('/add-symbol', methods=['POST'])
def add_symbol():
    symbol = request.form.get('symbol', '').upper().strip()
    if symbol:
        config = load_full_config()
        if symbol not in config['symbols']:
            config['symbols'].append(symbol)
            save_full_config(config)
            flash(f"Ticker {symbol} added to terminal.")
    return redirect(url_for('index'))

@app.route('/add-all-symbols', methods=['POST'])
def add_all_symbols():
    symbols = api.get_tradeable_assets()
    if symbols:
        config = load_full_config()
        config['symbols'] = list(set(config['symbols'] + symbols))
        save_full_config(config)
        flash(f"Imported {len(symbols)} assets.")
    return redirect(url_for('index'))

@app.route('/remove-symbol', methods=['POST'])
def remove_symbol():
    symbol = request.form.get('symbol')
    if symbol:
        config = load_full_config()
        if symbol in config['symbols']:
            config['symbols'].remove(symbol)
            save_full_config(config)
            flash(f"Removed {symbol}.")
    return redirect(url_for('index'))

@app.route('/update-stake', methods=['POST'])
def update_stake():
    config = load_full_config()
    config['stake_settings']['mode'] = request.form.get('mode')
    config['stake_settings']['fixed_amount'] = float(request.form.get('fixed_amount', 10.0))
    config['stake_settings']['percent_amount'] = float(request.form.get('percent_amount', 1.0))
    save_full_config(config)
    flash("Staking parameters synchronized.")
    return redirect(url_for('index'))

@app.route('/cancel-orders', methods=['POST'])
def cancel_orders():
    api.cancel_all_orders()
    flash("All pending orders purged.")
    return redirect(url_for('index'))

@app.route('/close-positions', methods=['POST'])
def close_positions():
    api.close_all_positions()
    with open('lots.json', 'w') as f:
        json.dump({}, f)
    flash("Portfolio liquidated and local state reset.")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
