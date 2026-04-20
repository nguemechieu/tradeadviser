import typer

app = typer.Typer()

@app.command()
def run():
    from src.core.engine import run_engine
    run_engine()

@app.command()
def backtest():
    print("Running backtest...")

if __name__ == "__main__":
    app()