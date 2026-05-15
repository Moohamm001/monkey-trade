import yfinance as yf
from typing import List, Optional
from .stock_data import get_stock_info, get_price_history
from .cycle_detector import detect_cycle

# Full S&P 500 constituent list (as of 2025)
SP500_TICKERS = [
    "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A","APD","ABNB","AKAM",
    "ALB","ARE","ALGN","ALLE","LNT","ALL","GOOGL","GOOG","MO","AMZN","AMCR","AEP",
    "AXP","AIG","AMT","AWK","AMP","AME","AMGN","APH","ADI","ANSS","AON","APA","AAPL",
    "AMAT","APTV","ACGL","ADM","ANET","AIZ","T","ATO","ADSK","AZO","AVB","AVY",
    "AXON","BKR","BALL","BAC","BK","BBWI","BAX","BDX","BRK-B","BBY","BIIB","BLK",
    "BX","BA","BKNG","BSX","BMY","AVGO","BR","BRO","BG","CDNS","CPT","CPB","COF",
    "CAH","KMX","CCL","CARR","CAT","CBOE","CBRE","CDW","CNC","CNP","CF","SCHW",
    "CHTR","CVX","CMG","CB","CHD","CI","CINF","CTAS","CSCO","C","CFG","CLX","CME",
    "CMS","KO","CTSH","CL","CMCSA","CAG","COP","ED","STZ","CEG","COO","CPRT","GLW",
    "CPAY","CTVA","CSGP","COST","CTRA","CRWD","CCI","CSX","CMI","CVS","DHR","DRI",
    "DVA","DE","DELL","DAL","DVN","DXCM","FANG","DLR","DFS","DG","DLTR","D","DPZ",
    "DOV","DOW","DHI","DTE","DUK","DD","EMN","ETN","EBAY","ECL","EIX","EW","EA",
    "ELV","EMR","ENPH","ETR","EOG","EPAM","EQT","EFX","EQIX","EQR","ESS","EL",
    "ETSY","EG","ES","EXC","EXPE","EXPD","EXR","XOM","FFIV","FDS","FICO","FAST",
    "FRT","FDX","FIS","FITB","FSLR","FE","FI","FMC","F","FTNT","FTV","FOXA","FOX",
    "BEN","FCX","GRMN","IT","GE","GEHC","GEN","GNRC","GD","GIS","GM","GPC","GILD",
    "GS","HAL","HIG","HAS","HCA","HSIC","HSY","HES","HPE","HLT","HOLX","HD","HON",
    "HRL","HST","HWM","HPQ","HUBB","HUM","HBAN","HII","IBM","IEX","IDXX","ITW",
    "INCY","IR","PODD","INTC","ICE","IFF","IP","IPG","INTU","ISRG","IVZ","INVH",
    "IQV","IRM","JBHT","JBL","JKHY","J","JNJ","JCI","JPM","JNPR","K","KVUE","KDP",
    "KEY","KEYS","KMB","KIM","KMI","KLAC","KHC","KR","LHX","LH","LRCX","LW","LVS",
    "LDOS","LEN","LIN","LYV","LKQ","LMT","L","LOW","LULU","LYB","MTB","MRO","MPC",
    "MKTX","MAR","MMC","MLM","MAS","MA","MTCH","MKC","MCD","MCK","MDT","MRK","META",
    "MET","MTD","MGM","MCHP","MU","MSFT","MAA","MRNA","MHK","MOH","TAP","MDLZ",
    "MPWR","MNST","MCO","MS","MOS","MSI","MSCI","NDAQ","NTAP","NFLX","NEM","NEE",
    "NKE","NI","NDSN","NSC","NTRS","NOC","NCLH","NRG","NUE","NVDA","NVR","NXPI",
    "ORLY","OXY","ODFL","OMC","ON","OKE","ORCL","OTIS","PCAR","PKG","PANW","PH",
    "PAYX","PAYC","PYPL","PNR","PEP","PFE","PCG","PM","PSX","PNW","PNC","POOL",
    "PPG","PPL","PFG","PG","PGR","PLD","PRU","PEG","PTC","PSA","PHM","PWR","QCOM",
    "DGX","RL","RJF","RTX","O","REG","REGN","RF","RSG","RMD","ROK","ROL","ROP",
    "ROST","RCL","SPGI","CRM","SBAC","SLB","STX","SRE","NOW","SHW","SPG","SWKS",
    "SJM","SNA","SO","LUV","SWK","SBUX","STT","STLD","STE","SYK","SYF","SNPS",
    "SYY","TMUS","TROW","TTWO","TPR","TRGP","TGT","TEL","TDY","TFX","TER","TSLA",
    "TXN","TJX","TSCO","TT","TDG","TRV","TRMB","TFC","TYL","TSN","USB","UBER",
    "UDR","ULTA","UNP","UAL","UPS","URI","UNH","UHS","VLO","VTR","VRSN","VRSK",
    "VZ","VRTX","V","VST","VMC","WMT","DIS","WM","WAT","WEC","WFC","WELL","WST",
    "WDC","WY","WHR","WMB","WTW","GWW","WYNN","XEL","XYL","YUM","ZBRA","ZBH","ZTS",
]

# Curated top-100 for faster "quick scan"
TOP100_TICKERS = [
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","BRK-B","AVGO","LLY",
    "JPM","V","MA","UNH","XOM","COST","JNJ","PG","HD","ABBV","BAC","KO","CRM",
    "MRK","CVX","AMD","NFLX","PEP","TMO","ADBE","ACN","WMT","LIN","DHR","TXN",
    "QCOM","PM","IBM","GE","RTX","INTC","CAT","INTU","AMGN","ISRG","GS","SPGI",
    "BKNG","VRTX","AXP","BX","SYK","GILD","PLD","LOW","MDT","NOW","AMAT","MU",
    "LRCX","KLAC","PANW","CRWD","C","MS","DE","BSX","UNP","SCHW","CB","TT",
    "SO","NEE","DUK","MCD","SBUX","CME","ICE","EQIX","ADI","CDNS","SNPS","ELV",
    "CI","MCO","MSI","NDAQ","APH","HCA","ITW","PGR","ZTS","AON","CTAS","WM",
    "ECL","NSC","ROP","FI","ETN","CSX","COF","OKE",
]


def screen_stocks(tickers: List[str], filters: dict) -> List[dict]:
    results = []
    for ticker in tickers:
        try:
            info = get_stock_info(ticker)
            if _passes_filters(info, filters):
                df = yf.Ticker(ticker).history(period="1y")
                if len(df) > 50:
                    cycle = detect_cycle(df)
                    info["cycle_stage"] = cycle["stage"]
                    info["cycle_confidence"] = cycle["confidence"]
                    info["stage_info"] = cycle["stage_info"]
                    # also filter by stage AFTER we have the stage
                    allowed = filters.get("cycle_stages")
                    if allowed and info["cycle_stage"] not in allowed:
                        continue
                results.append(info)
        except Exception:
            continue
    return results


def _passes_filters(info: dict, filters: dict) -> bool:
    rev_growth = info.get("revenue_growth")
    min_rev = filters.get("min_revenue_growth")
    if min_rev is not None and (rev_growth is None or rev_growth < min_rev / 100):
        return False

    earn_growth = info.get("earnings_growth")
    min_earn = filters.get("min_earnings_growth")
    if min_earn is not None and (earn_growth is None or earn_growth < min_earn / 100):
        return False

    pe = info.get("pe_ratio")
    max_pe = filters.get("max_pe")
    if max_pe is not None and pe is not None and pe > max_pe:
        return False

    mktcap = info.get("market_cap")
    min_mktcap = filters.get("min_market_cap")
    if min_mktcap is not None and (mktcap is None or mktcap < min_mktcap):
        return False

    net_margin = info.get("net_margins")
    min_margin = filters.get("min_net_margin")
    if min_margin is not None and (net_margin is None or net_margin < min_margin / 100):
        return False

    sectors = filters.get("sectors")
    if sectors and info.get("sector") not in sectors:
        return False

    return True
