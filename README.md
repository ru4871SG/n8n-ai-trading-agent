# AI Trading Agent with n8n

This project demonstrates how to create an AI agent workflow using n8n that can analyze different historical price actions, and make decision whether to trade your favorite instrument based on the analysis. If the agent decides that it's a good time to buy, it will automatically execute the trades based on the parameters that it sets in the same n8n workflow.

For this demonstration, I used `gemini-2.0-flash` from Gemini, since the API key was still free to use when I tested it the last time. I have a private repository where I swap the model from `gemini-2.0-flash` to my own finetuned model. Feel free to use the workflow and swap the model to your own preferred (or finetuned) model. You should also change the prompts for the AI to follow. 

The workflow itself is located in [n8n/ai_agent_n8n_workflow.json](n8n/ai_agent_n8n_workflow.json). You can import it to your n8n instance and start using it. It should look like the below image:

![Workflow in n8n](n8n/workflow.png)

This demonstration basically extracts stock market historical data from AlphaVantage (https://www.alphavantage.co/) and store it in Supabase database. The AI agent will then analyze your preferred stock historical data in Slack (using slash command), compare it against Bitcoin historical data (which is also stored in Supabase database), and decide whether it's a good time to buy Bitcoin or not based on the analysis. 

If the AI agent decides to buy, it will open a buy position on MEXC in the pair of WBTC/USDT (My API key allows me to trade WBTC/USDT on spot but not BTC). The agent will also set the Take Profit and Stop Loss parameters based on the analysis, and will automatically try to market sell the open position (of the same WBTC/USDT) when the price reaches the Take Profit or Stop Loss levels.

Now you are probably wondering, why do I use stock market analysis and compare it to Bitcoin historical data in order to predict Bitcoin price? It's because Bitcoin often follows the stock market trend, especially tech stocks. Not only that, since this is a demonstration, I want to use freely-available API to fetch historical data, and AlphaVantage provides really good historical daily data for free that you can store (also for free) in Supabase. 

You can, of course, swap the data sources from AlphaVantage to, let's say, more relevant data (such as Ethereum historical data or macroeconomic data) from other sources, you only need to change the sources in my extract script [vantage_extract.py](vantage_extract.py). If you choose to do so, don't forget to change the prompt in [ai_analyze_supabase_coinapi.py](ai_analyze_supabase_coinapi.py).

I also include a sample CSV file in the `bitcoin_daily_ohlc` folder, which contains Bitcoin daily OHLC data up to December 2023, which I got for free from Kraken. If you need more recent Bitcoin historical data, you have to look for different API sources on your own. The provided Bitcoin daily OHLC data in this repository is only available in csv format, and you can easily store it to Supabase using [kraken_csv_extract.py](kraken_csv_extract.py) script.

As for the trading platform, you can swap MEXC to your preferred trading platform, such as with Binance or other platforms that you prefer. Change them in [mexc_buy.py](mexc_buy.py) and [mexc_check_balance_and_sell.py](mexc_check_balance_and_sell.py). As of now, the second script is basically monitoring the open position and will try to market sell it when the price reaches the Take Profit or Stop Loss levels. Different trading platforms may provide more convenient way to put TP and SL levels directly, even in spot market.

In order to start the n8n workflow, you need to have a connected Slack application, and use the slash command `/analyze` to trigger the workflow. If you need a free request URL in the slash commands, you can use ngrok (https://ngrok.com/) to expose your local n8n instance to the internet.


**Note**: This repository is not intended to be used for real trading, especially if you don't have your own customized data and model. Using generic LLM like `gemini-2.0-flash` is not recommended for real trading, since its observational capabilities are extremely basic, very repetitive, and will often make super random recommendations.

I will update the README.md file with more details on how everything works.