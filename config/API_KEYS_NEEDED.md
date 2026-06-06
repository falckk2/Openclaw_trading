# API Keys — Required for BloFin Trading Bot

## Where to Get Your API Keys

1. Go to **https://blofin.com/account/apis**
2. Create a new API key
3. Copy the **API Key**, **Secret Key**, and **Passphrase**

## Where to Store Them

Edit `config/config.yaml` (copy from `config/demo_config.yaml`) and fill in:

```yaml
exchange:
  api_key: "YOUR_API_KEY"
  api_secret: "YOUR_API_SECRET"
  passphrase: "YOUR_PASSPHRASE"
```

**NEVER commit `config.yaml` to version control.** The file `config/.gitignore` excludes it.

## Permissions Required

For the trading bot, your API key needs:
- ✅ **READ** — view account info, balances, order history
- ✅ **TRADE** — place and cancel orders

## Demo Trading

Demo trading does NOT require API keys for market data (public endpoints).
For authenticated demo trading operations, demo API keys still work.

## Security Notes

- API keys are stored in plain text in `config/config.yaml`
- If you're concerned about security, use environment variables instead:
  ```python
  import os
  api_key = os.environ["BLOFIN_API_KEY"]
  ```
- Never share your API credentials
- Consider IP whitelisting if BloFin supports it
