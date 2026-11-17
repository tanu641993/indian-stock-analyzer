# src/ai_explainer.py

import ollama
import json

class AIExplainer:
    def __init__(self, model="phi3"):  # Default to phi3 for speed
        self.model = model

    def generate_explanation(self, stock_data):
        """Takes the stock scoring data and generates a single explanation"""
        system_prompt = (
            "You are a quantitative financial analyst. Your job is to explain a stock's score "
            "based strictly on the provided JSON data. Do NOT give buy/sell recommendations. "
            "Keep the explanation to 3 short sentences."
        )
        user_prompt = f"""
        Here is the scoring data for {stock_data.get('symbol')}:
        - Total Score: {stock_data.get('total_score')}/100
        - Component Scores: {json.dumps(stock_data.get('breakdown'))}
        - Risk Penalty: -{stock_data.get('risk_penalty')} points
        Explain why it received this score.
        """
        try:
            response = ollama.chat(model=self.model, messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ])
            return response['message']['content']
        except Exception as e:
            return f"⚠️ AI Connection Error: Ensure Ollama is running. Details: {e}"

    def chat_stream(self, user_question, df_rankings):
        """Streams the response for the chatbot to make it feel instant"""
        # 1. Reduce context: Only send the Top 5 stocks to save processing time
        top_5 = df_rankings.head(5)
        
        context_data = "Here are the Top 5 stocks from our scoring engine:\n"
        for index, row in top_5.iterrows():
            context_data += (
                f"- {row['Symbol']}: Score {row['Score']}/100 (Grade {row['Grade']}). "
                f"Model: {row['Model']}, Risk Penalty: -{row['Risk_Penalty']}\n"
            )

        system_prompt = (
            "You are an AI Stock Analyst. Answer the user's question using ONLY the provided Top 5 list. "
            "Be extremely concise (max 2 sentences). Do not give financial advice."
        )
        user_prompt = f"CONTEXT:\n{context_data}\n\nUSER QUESTION:\n{user_question}"

        try:
            # Use stream=True and keep_alive to keep model in memory
            stream = ollama.chat(
                model=self.model, 
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                stream=True,
                keep_alive="10m" 
            )
            
            for chunk in stream:
                yield chunk['message']['content']
                
        except Exception as e:
            yield f"⚠️ AI Error: Ensure Ollama is running. Details: {e}"