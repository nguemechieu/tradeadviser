import typer

app = typer.Typer()

@app.command()
def run():
    from desktop.src.backtesting.backtest_engine import  BacktestEngine
    backtest_engine = BacktestEngine()
    backtest_engine.run()


@app.command()
def backtest():
    print("Running backtest...")

if __name__ == "__main__":
    app()