# Windows one-click setup

Use this when giving the app to a non-technical Windows user.

## Make the package

On your computer, double-click:

```text
Create Friend Package.bat
```

It creates:

```text
dist\AI-Portfolio-Advisor-Windows.zip
```

Send that zip file to your friend.

## Friend instructions

1. Extract the zip file.
2. Double-click `Start AI Portfolio Advisor.bat`.
3. If asked, allow Docker Desktop to install and finish setup.
4. The app opens automatically at `http://localhost:3000`.

To stop the app, double-click `Stop AI Portfolio Advisor.bat`.

## Notes

- Docker Desktop is required. The start script can install it with `winget` on most modern Windows laptops.
- The first start can take several minutes because Docker downloads and builds everything.
- No separate Node, Python, Postgres, or Redis install is needed.
- If Zerodha, Gemini, OpenAI, Alpha Vantage, or Finnhub keys are needed, use the in-app configuration where available or edit `.env` after the first start and run `Start AI Portfolio Advisor.bat` again.
