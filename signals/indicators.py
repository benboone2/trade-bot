"""
Pure indicator functions. All inputs are lists of floats (closing prices),
ordered oldest → newest. No external dependencies.
"""


def sma(prices: list[float], period: int) -> float:
    if len(prices) < period:
        raise ValueError(f"Need at least {period} prices for SMA({period}), got {len(prices)}")
    return sum(prices[-period:]) / period


def ema(prices: list[float], period: int) -> float:
    """Standard EMA seeded with the SMA of the first `period` values."""
    if len(prices) < period:
        raise ValueError(f"Need at least {period} prices for EMA({period}), got {len(prices)}")

    multiplier = 2.0 / (period + 1)
    result = sum(prices[:period]) / period  # seed with SMA

    for price in prices[period:]:
        result = price * multiplier + result * (1 - multiplier)

    return result


def ema_series(prices: list[float], period: int) -> list[float]:
    """Returns a full EMA series (one value per input price after the seed period)."""
    if len(prices) < period:
        raise ValueError(f"Need at least {period} prices for EMA({period}), got {len(prices)}")

    multiplier = 2.0 / (period + 1)
    seed = sum(prices[:period]) / period
    series = [seed]

    for price in prices[period:]:
        series.append(price * multiplier + series[-1] * (1 - multiplier))

    return series


def rsi(prices: list[float], period: int = 14) -> float:
    """
    Wilder's RSI. Returns a value between 0 and 100.
    Needs at least period + 1 prices.
    """
    if len(prices) < period + 1:
        raise ValueError(f"Need at least {period + 1} prices for RSI({period}), got {len(prices)}")

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(c, 0.0) for c in changes]
    losses = [abs(min(c, 0.0)) for c in changes]

    # Seed with simple average of first `period` values
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder smoothing for remaining values
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def sma_series(prices: list[float], period: int) -> list[float]:
    """Returns one SMA value per position starting at index `period - 1`."""
    if len(prices) < period:
        raise ValueError(f"Need at least {period} prices for SMA({period}), got {len(prices)}")
    return [sum(prices[i:i + period]) / period for i in range(len(prices) - period + 1)]
