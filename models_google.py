from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union, List
import os
import pathlib
from pathlib import Path
from dotenv import load_dotenv
from google import genai  # Google Generative AI Python SDK
import time
import logging
from file_store import register_file, get_provider_file_id, register_provider_upload

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please check your .env file.")

# Configure Google Generative AI client
client = genai.Client(api_key=api_key)

# Available Google models for benchmarking
AVAILABLE_MODELS = [
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro-preview-05-06",
    # "imagen-3.0-generate-002",
]

"""web search
The Grounding with Google Search feature in the Gemini API and AI Studio can be used to improve the accuracy and recency of responses from the model. In addition to more factual responses, when Grounding with Google Search is enabled, the Gemini API returns grounding sources (in-line supporting links) and Google Search Suggestions along with the response content. The Search Suggestions point users to the search results corresponding to the grounded response.

This guide will help you get started with Grounding with Google Search.

Before you begin
Before calling the Gemini API, ensure you have your SDK of choice installed, and a Gemini API key configured and ready to use.

Configure Search Grounding
Starting with Gemini 2.0, Google Search is available as a tool. This means that the model can decide when to use Google Search. The following example shows how to configure Search as a tool.


from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

client = genai.Client()
model_id = "gemini-2.0-flash"

google_search_tool = Tool(
    google_search = GoogleSearch()
)

response = client.models.generate_content(
    model=model_id,
    contents="When is the next total solar eclipse in the United States?",
    config=GenerateContentConfig(
        tools=[google_search_tool],
        response_modalities=["TEXT"],
    )
)

for each in response.candidates[0].content.parts:
    print(each.text)
# Example response:
# The next total solar eclipse visible in the contiguous United States will be on ...

# To get grounding metadata as web content.
print(response.candidates[0].grounding_metadata.search_entry_point.rendered_content)
The Search-as-a-tool functionality also enables multi-turn searches. Combining Search with function calling is not yet supported.

Search as a tool enables complex prompts and workflows that require planning, reasoning, and thinking:

Grounding to enhance factuality and recency and provide more accurate answers
Retrieving artifacts from the web to do further analysis on
Finding relevant images, videos, or other media to assist in multimodal reasoning or generation tasks
Coding, technical troubleshooting, and other specialized tasks
Finding region-specific information or assisting in translating content accurately
Finding relevant websites for further browsing
Grounding with Google Search works with all available languages when doing text prompts. On the paid tier of the Gemini Developer API, you can get 1,500 Grounding with Google Search queries per day for free, with additional queries billed at the standard $35 per 1,000 queries.

You can learn more by trying the Search tool notebook.

Google Search Suggestions
To use Grounding with Google Search, you have to display Google Search Suggestions, which are suggested queries included in the metadata of the grounded response. To learn more about the display requirements, see Use Google Search Suggestions.

Google Search retrieval
Note: Google Search retrieval is only compatible with Gemini 1.5 models. For Gemini 2.0 models, you should use Search as a tool.
To configure a model to use Google Search retrieval, pass in the appropriate tool.

Note that Google Search retrieval is only compatible with the 1.5 models, later models need to use the Search Grounding. If you try to use it, the SDK will convert your code to use the Search Grounding instead and will ignore the dynamic threshold settings.

Getting started

from google import genai
from google.genai import types

client = genai.Client(api_key="GEMINI_API_KEY")

response = client.models.generate_content(
    model='gemini-1.5-flash',
    contents="Who won the US open this year?",
    config=types.GenerateContentConfig(
        tools=[types.Tool(
            google_search_retrieval=types.GoogleSearchRetrieval()
        )]
    )
)
print(response)

Prediction score: When you request a grounded answer, Gemini assigns a prediction score to the prompt. The prediction score is a floating point value in the range [0,1]. Its value depends on whether the prompt can benefit from grounding the answer with the most up-to-date information from Google Search. Thus, if a prompt requires an answer grounded in the most recent facts on the web, it has a higher prediction score. A prompt for which a model-generated answer is sufficient has a lower prediction score.

Here are examples of some prompts and their prediction scores.

Note: The prediction scores are assigned by Gemini and can vary over time depending on several factors.
Prompt	Prediction score	Comment
"Write a poem about peonies"	0.13	The model can rely on its knowledge and the answer doesn't need grounding.
"Suggest a toy for a 2yo child"	0.36	The model can rely on its knowledge and the answer doesn't need grounding.
"Can you give a recipe for an asian-inspired guacamole?"	0.55	Google Search can give a grounded answer, but grounding isn't strictly required; the model knowledge might be sufficient.
"What's Agent Builder? How is grounding billed in Agent Builder?"	0.72	Requires Google Search to generate a well-grounded answer.
"Who won the latest F1 grand prix?"	0.97	Requires Google Search to generate a well-grounded answer.
Threshold: In your API request, you can specify a dynamic retrieval configuration with a threshold. The threshold is a floating point value in the range [0,1] and defaults to 0.3. If the threshold value is zero, the response is always grounded with Google Search. For all other values of threshold, the following is applicable:

If the prediction score is greater than or equal to the threshold, the answer is grounded with Google Search. A lower threshold implies that more prompts have responses that are generated using Grounding with Google Search.
If the prediction score is less than the threshold, the model might still generate the answer, but it isn't grounded with Google Search.
To learn how to set the dynamic retrieval threshold using an SDK or the REST API, see the appropriate code example.

To find a good threshold that suits your business needs, you can create a representative set of queries that you expect to encounter. Then you can sort the queries according to the prediction score in the response and select a good threshold for your use case.

A grounded response
If your prompt successfully grounds to Google Search, the response will include groundingMetadata. A grounded response might look something like this (parts of the response have been omitted for brevity):


{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "Carlos Alcaraz won the Gentlemen's Singles title at the 2024 Wimbledon Championships. He defeated Novak Djokovic in the final, winning his second consecutive Wimbledon title and fourth Grand Slam title overall. \n"
          }
        ],
        "role": "model"
      },
      ...
      "groundingMetadata": {
        "searchEntryPoint": {
          "renderedContent": "\u003cstyle\u003e\n.container {\n  align-items: center;\n  border-radius: 8px;\n  display: flex;\n  font-family: Google Sans, Roboto, sans-serif;\n  font-size: 14px;\n  line-height: 20px;\n  padding: 8px 12px;\n}\n.chip {\n  display: inline-block;\n  border: solid 1px;\n  border-radius: 16px;\n  min-width: 14px;\n  padding: 5px 16px;\n  text-align: center;\n  user-select: none;\n  margin: 0 8px;\n  -webkit-tap-highlight-color: transparent;\n}\n.carousel {\n  overflow: auto;\n  scrollbar-width: none;\n  white-space: nowrap;\n  margin-right: -12px;\n}\n.headline {\n  display: flex;\n  margin-right: 4px;\n}\n.gradient-container {\n  position: relative;\n}\n.gradient {\n  position: absolute;\n  transform: translate(3px, -9px);\n  height: 36px;\n  width: 9px;\n}\n@media (prefers-color-scheme: light) {\n  .container {\n    background-color: #fafafa;\n    box-shadow: 0 0 0 1px #0000000f;\n  }\n  .headline-label {\n    color: #1f1f1f;\n  }\n  .chip {\n    background-color: #ffffff;\n    border-color: #d2d2d2;\n    color: #5e5e5e;\n    text-decoration: none;\n  }\n  .chip:hover {\n    background-color: #f2f2f2;\n  }\n  .chip:focus {\n    background-color: #f2f2f2;\n  }\n  .chip:active {\n    background-color: #d8d8d8;\n    border-color: #b6b6b6;\n  }\n  .logo-dark {\n    display: none;\n  }\n  .gradient {\n    background: linear-gradient(90deg, #fafafa 15%, #fafafa00 100%);\n  }\n}\n@media (prefers-color-scheme: dark) {\n  .container {\n    background-color: #1f1f1f;\n    box-shadow: 0 0 0 1px #ffffff26;\n  }\n  .headline-label {\n    color: #fff;\n  }\n  .chip {\n    background-color: #2c2c2c;\n    border-color: #3c4043;\n    color: #fff;\n    text-decoration: none;\n  }\n  .chip:hover {\n    background-color: #353536;\n  }\n  .chip:focus {\n    background-color: #353536;\n  }\n  .chip:active {\n    background-color: #464849;\n    border-color: #53575b;\n  }\n  .logo-light {\n    display: none;\n  }\n  .gradient {\n    background: linear-gradient(90deg, #1f1f1f 15%, #1f1f1f00 100%);\n  }\n}\n\u003c/style\u003e\n\u003cdiv class=\"container\"\u003e\n  \u003cdiv class=\"headline\"\u003e\n    \u003csvg class=\"logo-light\" width=\"18\" height=\"18\" viewBox=\"9 9 35 35\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\"\u003e\n      \u003cpath fill-rule=\"evenodd\" clip-rule=\"evenodd\" d=\"M42.8622 27.0064C42.8622 25.7839 42.7525 24.6084 42.5487 23.4799H26.3109V30.1568H35.5897C35.1821 32.3041 33.9596 34.1222 32.1258 35.3448V39.6864H37.7213C40.9814 36.677 42.8622 32.2571 42.8622 27.0064V27.0064Z\" fill=\"#4285F4\"/\u003e\n      \u003cpath fill-rule=\"evenodd\" clip-rule=\"evenodd\" d=\"M26.3109 43.8555C30.9659 43.8555 34.8687 42.3195 37.7213 39.6863L32.1258 35.3447C30.5898 36.3792 28.6306 37.0061 26.3109 37.0061C21.8282 37.0061 18.0195 33.9811 16.6559 29.906H10.9194V34.3573C13.7563 39.9841 19.5712 43.8555 26.3109 43.8555V43.8555Z\" fill=\"#34A853\"/\u003e\n      \u003cpath fill-rule=\"evenodd\" clip-rule=\"evenodd\" d=\"M16.6559 29.8904C16.3111 28.8559 16.1074 27.7588 16.1074 26.6146C16.1074 25.4704 16.3111 24.3733 16.6559 23.3388V18.8875H10.9194C9.74388 21.2072 9.06992 23.8247 9.06992 26.6146C9.06992 29.4045 9.74388 32.022 10.9194 34.3417L15.3864 30.8621L16.6559 29.8904V29.8904Z\" fill=\"#FBBC05\"/\u003e\n      \u003cpath fill-rule=\"evenodd\" clip-rule=\"evenodd\" d=\"M26.3109 16.2386C28.85 16.2386 31.107 17.1164 32.9095 18.8091L37.8466 13.8719C34.853 11.082 30.9659 9.3736 26.3109 9.3736C19.5712 9.3736 13.7563 13.245 10.9194 18.8875L16.6559 23.3388C18.0195 19.2636 21.8282 16.2386 26.3109 16.2386V16.2386Z\" fill=\"#EA4335\"/\u003e\n    \u003c/svg\u003e\n    \u003csvg class=\"logo-dark\" width=\"18\" height=\"18\" viewBox=\"0 0 48 48\" xmlns=\"http://www.w3.org/2000/svg\"\u003e\n      \u003ccircle cx=\"24\" cy=\"23\" fill=\"#FFF\" r=\"22\"/\u003e\n      \u003cpath d=\"M33.76 34.26c2.75-2.56 4.49-6.37 4.49-11.26 0-.89-.08-1.84-.29-3H24.01v5.99h8.03c-.4 2.02-1.5 3.56-3.07 4.56v.75l3.91 2.97h.88z\" fill=\"#4285F4\"/\u003e\n      \u003cpath d=\"M15.58 25.77A8.845 8.845 0 0 0 24 31.86c1.92 0 3.62-.46 4.97-1.31l4.79 3.71C31.14 36.7 27.65 38 24 38c-5.93 0-11.01-3.4-13.45-8.36l.17-1.01 4.06-2.85h.8z\" fill=\"#34A853\"/\u003e\n      \u003cpath d=\"M15.59 20.21a8.864 8.864 0 0 0 0 5.58l-5.03 3.86c-.98-2-1.53-4.25-1.53-6.64 0-2.39.55-4.64 1.53-6.64l1-.22 3.81 2.98.22 1.08z\" fill=\"#FBBC05\"/\u003e\n      \u003cpath d=\"M24 14.14c2.11 0 4.02.75 5.52 1.98l4.36-4.36C31.22 9.43 27.81 8 24 8c-5.93 0-11.01 3.4-13.45 8.36l5.03 3.85A8.86 8.86 0 0 1 24 14.14z\" fill=\"#EA4335\"/\u003e\n    \u003c/svg\u003e\n    \u003cdiv class=\"gradient-container\"\u003e\u003cdiv class=\"gradient\"\u003e\u003c/div\u003e\u003c/div\u003e\n  \u003c/div\u003e\n  \u003cdiv class=\"carousel\"\u003e\n    \u003ca class=\"chip\" href=\"https://vertexaisearch.cloud.google.com/grounding-api-redirect/AWhgh4x8Epe-gzpwRBvp7o3RZh2m1ygq1EHktn0OWCtvTXjad4bb1zSuqfJd6OEuZZ9_SXZ_P2SvCpJM7NaFfQfiZs6064MeqXego0vSbV9LlAZoxTdbxWK1hFeqTG6kA13YJf7Fbu1SqBYM0cFM4zo0G_sD9NKYWcOCQMvDLDEJFhjrC9DM_QobBIAMq-gWN95G5tvt6_z6EuPN8QY=\"\u003ewho won wimbledon 2024\u003c/a\u003e\n  \u003c/div\u003e\n\u003c/div\u003e\n"
        },
        "groundingChunks": [
          {
            "web": {
              "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AWhgh4whET1ta3sDETZvcicd8FeNe4z0VuduVsxrT677KQRp2rYghXI0VpfYbIMVI3THcTuMwggRCbFXS_wVvW0UmGzMe9h2fyrkvsnQPJyikJasNIbjJLPX0StM4Bd694-ZVle56MmRA4YiUvwSqad1w6O2opmWnw==",
              "title": "wikipedia.org"
            }
          },
          {
            "web": {
              "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AWhgh4wR1M-9-yMPUr_KdHlnoAmQ8ZX90DtQ_vDYTjtP2oR5RH4tRP04uqKPLmesvo64BBkPeYLC2EpVDxv9ngO3S1fs2xh-e78fY4m0GAtgNlahUkm_tBm_sih5kFPc7ill9u2uwesNGUkwrQlmP2mfWNU5lMMr23HGktr6t0sV0QYlzQq7odVoBxYWlQ_sqWFH",
              "title": "wikipedia.org"
            }
          },
          {
            "web": {
              "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AWhgh4wsDmROzbP-tmt8GdwCW_pqISTZ4IRbBuoaMyaHfcQg8WW-yKRQQvMDTPAuLxJh-8_U8_iw_6JKFbQ8M9oVYtaFdWFK4gOtL4RrC9Jyqc5BNpuxp6uLEKgL5-9TggtNvO97PyCfziDFXPsxylwI1HcfQdrz3Jy7ZdOL4XM-S5rC0lF2S3VWW0IEAEtS7WX861meBYVjIuuF_mIr3spYPqWLhbAY2Spj-4_ba8DjRvmevIFUhRuESTKvBfmpxNSM",
              "title": "cbssports.com"
            }
          },
          {
            "web": {
              "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AWhgh4yzjLkorHiUKjhOPkWaZ9b4cO-cLG-02vlEl6xTBjMUjyhK04qSIclAa7heR41JQ6AAVXmNdS3WDrLOV4Wli-iezyzW8QPQ4vgnmO_egdsuxhcGk3-Fp8-yfqNLvgXFwY5mPo6QRhvplOFv0_x9mAcka18QuAXtj0SPvJfZhUEgYLCtCrucDS5XFc5HmRBcG1tqFdKSE1ihnp8KLdaWMhrUQI21hHS9",
              "title": "jagranjosh.com"
            }
          },
          {
            "web": {
              "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AWhgh4y9L4oeNGWCatFz63b9PpP3ys-Wi_zwnkUT5ji9lY7gPUJQcsmmE87q88GSdZqzcx5nZG9usot5FYk2yK-FAGvCRE6JsUQJB_W11_kJU2HVV1BTPiZ4SAgm8XDFIxpCZXnXmEx5HUfRqQm_zav7CvS2qjA2x3__qLME6Jy7R5oza1C5_aqjQu422le9CaigThS5bvJoMo-ZGcXdBUCj2CqoXNVjMA==",
              "title": "apnews.com"
            }
          }
        ],
        "groundingSupports": [
          {
            "segment": {
              "endIndex": 85,
              "text": "Carlos Alcaraz won the Gentlemen's Singles title at the 2024 Wimbledon Championships."
            },
            "groundingChunkIndices": [
              0,
              1,
              2,
              3
            ],
            "confidenceScores": [
              0.97380733,
              0.97380733,
              0.97380733,
              0.97380733
            ]
          },
          {
            "segment": {
              "startIndex": 86,
              "endIndex": 210,
              "text": "He defeated Novak Djokovic in the final, winning his second consecutive Wimbledon title and fourth Grand Slam title overall."
            },
            "groundingChunkIndices": [
              1,
              0,
              4
            ],
            "confidenceScores": [
              0.96145374,
              0.96145374,
              0.96145374
            ]
          }
        ],
        "webSearchQueries": [
          "who won wimbledon 2024"
        ]
      }
    }
  ],
  ...
}
If the response doesn't include groundingMetadata, this means the response wasn't successfully grounded. There are several reasons this could happen, including low source relevance or incomplete information within the model response.

When a grounded result is generated, the metadata contains URIs that redirect to the publishers of the content that was used to generate the grounded result. These URIs contain the vertexaisearch subdomain, as in this truncated example: https://vertexaisearch.cloud.google.com/grounding-api-redirect/.... The metadata also contains the publishers' domains. The provided URIs remain accessible for 30 days after the grounded result is generated.

Important: The provided URIs must be directly accessible by the end users and must not be queried programmatically through automated means. If automated access is detected, the grounded answer generation service might stop providing the redirection URIs.
The renderedContent field within searchEntryPoint is the provided code for implementing Google Search Suggestions. See Use Google Search Suggestions to learn more."""

"""gemini 2.5 pro pricing
Gemini 2.5 Pro Preview
Try it in Google AI Studio

Our state-of-the-art multipurpose model, which excels at coding and complex reasoning tasks.

Preview models may change before becoming stable and have more restrictive rate limits.

Free Tier	Paid Tier, per 1M tokens in USD
Input price	Not available	$1.25, prompts <= 200k tokens
$2.50, prompts > 200k tokens
Output price (including thinking tokens)	Not available	$10.00, prompts <= 200k tokens
$15.00, prompts > 200k
Context caching price	Not available	$0.31, prompts <= 200k tokens
$0.625, prompts > 200k
$4.50 / 1,000,000 tokens per hour
Grounding with Google Search	Not available	1,500 RPD (free), then $35 / 1,000 requests
Text-to-speech
(gemini-2.5-pro-preview-tts)	Free of charge	$1.00 (Input)
$20.00 (Output)
Used to improve our products	Yes	No"""


"""gemini 2.5 flash pricing
Gemini 2.5 Flash Preview
Try it in Google AI Studio

Our first hybrid reasoning model which supports a 1M token context window and has thinking budgets.

Preview models may change before becoming stable and have more restrictive rate limits.

Free Tier	Paid Tier, per 1M tokens in USD
Input price	Free of charge	$0.15 (text / image / video)
$1.00 (audio)
Output price	Free of charge	Non-thinking: $0.60
Thinking: $3.50
Context caching price	Not available	$0.0375 (text / image / video)
$0.25 (audio)
$1.00 / 1,000,000 tokens per hour
Grounding with Google Search	Free of charge, up to 500 RPD	1,500 RPD (free), then $35 / 1,000 requests
Text-to-speech
(gemini-2.5-flash-preview-tts)	Free of charge	$0.50 (Input)
$10.00 (Output)
Used to improve our products	Yes	No"""

"""token counting guide

Context windows
The models available through the Gemini API have context windows that are measured in tokens. The context window defines how much input you can provide and how much output the model can generate. You can determine the size of the context window by calling the getModels endpoint or by looking in the models documentation.

In the following example, you can see that the gemini-1.5-flash model has an input limit of about 1,000,000 tokens and an output limit of about 8,000 tokens, which means a context window is 1,000,000 tokens.


from google import genai

client = genai.Client()
model_info = client.models.get(model="gemini-2.0-flash")
print(f"{model_info.input_token_limit=}")
print(f"{model_info.output_token_limit=}")
# ( e.g., input_token_limit=30720, output_token_limit=2048 )

Count tokens
All input to and output from the Gemini API is tokenized, including text, image files, and other non-text modalities.

You can count tokens in the following ways:

Call count_tokens with the input of the request.
This returns the total number of tokens in the input only. You can make this call before sending the input to the model to check the size of your requests.

Use the usage_metadata attribute on the response object after calling generate_content.
This returns the total number of tokens in both the input and the output: total_token_count.
It also returns the token counts of the input and output separately: prompt_token_count (input tokens) and candidates_token_count (output tokens).

Count text tokens
If you call count_tokens with a text-only input, it returns the token count of the text in the input only (total_tokens). You can make this call before calling generate_content to check the size of your requests.

Another option is calling generate_content and then using the usage_metadata attribute on the response object to get the following:

The separate token counts of the input (prompt_token_count) and the output (candidates_token_count)
The total number of tokens in both the input and the output (total_token_count)

from google import genai

client = genai.Client()
prompt = "The quick brown fox jumps over the lazy dog."

# Count tokens using the new client method.
total_tokens = client.models.count_tokens(
    model="gemini-2.0-flash", contents=prompt
)
print("total_tokens: ", total_tokens)
# ( e.g., total_tokens: 10 )

response = client.models.generate_content(
    model="gemini-2.0-flash", contents=prompt
)

# The usage_metadata provides detailed token counts.
print(response.usage_metadata)
# ( e.g., prompt_token_count: 11, candidates_token_count: 73, total_token_count: 84 )

Count multimodal tokens
All input to the Gemini API is tokenized, including text, image files, and other non-text modalities. Note the following high-level key points about tokenization of multimodal input during processing by the Gemini API:

With Gemini 2.0, image inputs with both dimensions <=384 pixels are counted as 258 tokens. Images larger in one or both dimensions are cropped and scaled as needed into tiles of 768x768 pixels, each counted as 258 tokens. Prior to Gemini 2.0, images used a fixed 258 tokens.

Video and audio files are converted to tokens at the following fixed rates: video at 263 tokens per second and audio at 32 tokens per second.

Image files
If you call count_tokens with a text-and-image input, it returns the combined token count of the text and the image in the input only (total_tokens). You can make this call before calling generate_content to check the size of your requests. You can also optionally call count_tokens on the text and the file separately.

Another option is calling generate_content and then using the usage_metadata attribute on the response object to get the following:

The separate token counts of the input (prompt_token_count) and the output (candidates_token_count)
The total number of tokens in both the input and the output (total_token_count)
Note: You'll get the same token count if you use a file uploaded using the File API or you provide the file as inline data.
Example that uses an uploaded image from the File API:


from google import genai

client = genai.Client()
prompt = "Tell me about this image"
your_image_file = client.files.upload(file=media / "organ.jpg")

print(
    client.models.count_tokens(
        model="gemini-2.0-flash", contents=[prompt, your_image_file]
    )
)
# ( e.g., total_tokens: 263 )

response = client.models.generate_content(
    model="gemini-2.0-flash", contents=[prompt, your_image_file]
)
print(response.usage_metadata)
# ( e.g., prompt_token_count: 264, candidates_token_count: 80, total_token_count: 345 )

System instructions and tools
System instructions and tools also count towards the total token count for the input.

If you use system instructions, the total_tokens count increases to reflect the addition of system_instruction.

If you use function calling, the total_tokens count increases to reflect the addition of tools."""

COSTS = {
    "gemini-2.5-flash-preview-05-20": {
        "input": 0.15,  # $0.15 per 1M tokens for text/image/video
        "input_audio": 1.00,  # $1.00 per 1M tokens for audio
        "cached": 0.0375,  # $0.0375 per 1M tokens for text/image/video
        "cached_audio": 0.25,  # $0.25 per 1M tokens for audio
        "output_non_thinking": 0.60,  # $0.60 per 1M tokens for non-thinking output
        "output_thinking": 3.50,  # $3.50 per 1M tokens for thinking output
        "search_cost": 0.035,  # $35 per 1k requests
        "cache_storage": 1.00  # $1.00 per 1M tokens per hour
    },
    "gemini-2.5-pro-preview-05-06": {
        "input_small": 1.25,  # $1.25 per 1M tokens for prompts <= 200k tokens
        "input_large": 2.50,  # $2.50 per 1M tokens for prompts > 200k tokens
        "cached_small": 0.31,  # $0.31 per 1M tokens for prompts <= 200k tokens
        "cached_large": 0.625,  # $0.625 per 1M tokens for prompts > 200k tokens
        "output_small": 10.00,  # $10.00 per 1M tokens for prompts <= 200k tokens
        "output_large": 15.00,  # $15.00 per 1M tokens for prompts > 200k tokens
        "search_cost": 0.035,  # $35 per 1k requests
        "cache_storage": 4.50  # $4.50 per 1M tokens per hour
    }
}

IMAGE_COST = 0.03

"""Gemini context windows (all gemini models)

Input token limit

1,048,576

token counting

from google import genai

client = genai.Client()
prompt = "The quick brown fox jumps over the lazy dog."

# Count tokens using the new client method.
total_tokens = client.models.count_tokens(
    model="gemini-2.0-flash", contents=prompt
)
print("total_tokens: ", total_tokens)
# ( e.g., total_tokens: 10 )
"""

def ensure_file_uploaded(file_path: Path, db_path: Path = Path.cwd()) -> str:
    """
    Ensure a file is uploaded to Google and return the provider file ID.
    Uses the new multi-provider file system to avoid duplicate uploads.
    
    Args:
        file_path: Path to the file to upload
        db_path: Path to the database directory
        
    Returns:
        provider_file_id: The Google file ID for this file
    """
    # Register file in our central registry
    file_id = register_file(file_path, db_path)
    
    # Check if this file has already been uploaded to Google
    provider_file_id = get_provider_file_id(file_id, "google", db_path)
    
    if provider_file_id:
        logging.info(f"File {file_path.name} already uploaded to Google with ID {provider_file_id}")
        return provider_file_id
    
    # File hasn't been uploaded to Google yet, upload it now
    logging.info(f"Uploading {file_path.name} to Google for the first time")
    provider_file_id = google_upload(file_path)
    
    # Register the upload in our database
    register_provider_upload(file_id, "google", provider_file_id, db_path)
    
    return provider_file_id

def google_upload(pdf_path: Path) -> str:
    """
    Upload a PDF file to Google Generative AI and return the file ID.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        str: File ID for the uploaded PDF
        
    Raises:
        Exception: If upload fails
    """    
    try:
        # Upload file to Google
        uploaded_file = client.files.upload(
            file=pdf_path,
            config=dict(mime_type='application/pdf')
        )
        
        # Get the file name (which serves as the ID)
        file_id = uploaded_file.name
        
        logging.info(f"Successfully uploaded {pdf_path.name} to Google. File ID: {file_id}")
        return file_id
    
    except Exception as e:
        logging.error(f"Error uploading {pdf_path} to Google: {e}")
        raise Exception(f"Failed to upload PDF to Google: {str(e)}")

def google_ask_with_files(file_paths: List[Path], prompt_text: str, model_name: str = "gemini-1.5-flash", db_path: Path = Path.cwd(), web_search: bool = False) -> Tuple[str, int, int, int, bool, str]:
    """
    Send a query to a Google Gemini model with multiple file attachments.
    
    Args:
        file_paths: List of paths to files to include
        prompt_text: The question to ask the model
        model_name: The model to use (e.g., "gemini-1.5-flash")
        db_path: Path to the database directory
        web_search: Whether to enable web search for this prompt
        
    Returns:
        A tuple containing:
            - answer (str): The model's text response
            - standard_input_tokens (int): Tokens used in the input
            - cached_input_tokens (int): Cached tokens used
            - output_tokens (int): Tokens used in the output (includes thinking tokens)
            - web_search_used (bool): Whether web search was actually used
            - web_search_sources (str): Raw web search data as string
    """
    # Build content list with files and prompt
    content_parts = []
    
    # Add files to content
    for file_path in file_paths:
        # Generate the part for this file
        part_id = ensure_file_uploaded(file_path, db_path)
        content_parts.append({"file_data": {"file_uri": part_id, "mime_type": "application/pdf"}})
    
    # Add prompt text
    content_parts.append({"text": prompt_text})
    
    # Create the content object
    contents = [{"parts": content_parts}]
    
    return google_ask_internal(contents, model_name, web_search)

def google_ask_internal(contents: List, model_name: str, web_search: bool = False) -> Tuple[str, int, int, int, bool, str]:
    """
    Internal function to send a query to Google with prepared contents.
    
    Returns:
        A tuple containing:
            - answer (str): The model's text response
            - standard_input_tokens (int): Tokens used in the input
            - cached_input_tokens (int): Cached tokens used
            - output_tokens (int): Tokens used in the output (includes thinking tokens)
            - web_search_used (bool): Whether web search was actually used
            - web_search_sources (str): Raw web search data as string
    """
    # Add direct console output for high visibility
    print(f"\n🔄 GOOGLE API CALL STARTING - MODEL: {model_name}")
    print(f"   Contents: {len(contents)} items")
    if web_search:
        print("   Web search enabled")
    
    logging.info(f"===== GOOGLE_ASK_INTERNAL FUNCTION CALLED =====")
    logging.info(f"Arguments: model_name={model_name}, web_search={web_search}")
    
    try:
        # Prepare tools for web search if enabled
        generation_config = {}
        tools = []
        
        if web_search:
            from google.genai.types import Tool, GoogleSearch
            tools.append(Tool(google_search=GoogleSearch()))
        
        # Send request to Google API
        try:
            # Prepare generation config
            generation_config = {
                "temperature": 0.2,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048
            }
            
            # Create generation config
            from google.genai.types import GenerateContentConfig
            config = GenerateContentConfig(
                temperature=generation_config.get("temperature", 0.2),
                top_p=generation_config.get("top_p", 0.8),
                top_k=generation_config.get("top_k", 40),
                max_output_tokens=generation_config.get("max_output_tokens", 2048),
                tools=tools if web_search else None,
                response_modalities=["TEXT"]
            )
            
            # Generate content using the client directly
            response = client.models.generate_content(
                model=model_name,
                contents=contents, 
                config=config
            )
            
            # Parse response
            tokens_metadata = response.usage_metadata
            
            standard_input_tokens = tokens_metadata.prompt_token_count
            cached_input_tokens = 0  # Google doesn't report cached tokens separately
            output_tokens = tokens_metadata.candidates_token_count
            
            # Detect web search usage by checking if tools were used
            web_search_used = False
            web_search_queries = 0
            web_search_content = ""
            
            # Only count as web search if we explicitly enabled it AND grounding was found
            # Google models may automatically use grounding, but we only count it as "web search"
            # if the user explicitly requested it
            if web_search:
                # Check if the response contains web search results and extract content
                if hasattr(response, 'candidates') and response.candidates:
                    for candidate in response.candidates:
                        if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                            web_search_used = True
                            web_search_queries = 1
                            
                            # Extract grounding content for token counting and sources
                            if hasattr(candidate.grounding_metadata, 'grounding_chunks'):
                                for chunk in candidate.grounding_metadata.grounding_chunks:
                                    if hasattr(chunk, 'web') and hasattr(chunk.web, 'title'):
                                        web_search_content += f"Title: {chunk.web.title}\n"
                                        if hasattr(chunk.web, 'uri'):
                                            web_search_content += f"URL: {chunk.web.uri}\n"
                                        web_search_content += "---\n"
                            
                            # Extract search entry point content (this contains most of the grounding data)
                            if hasattr(candidate.grounding_metadata, 'search_entry_point'):
                                entry_point = candidate.grounding_metadata.search_entry_point
                                if hasattr(entry_point, 'rendered_content'):
                                    web_search_content += f"Search entry point:\n{entry_point.rendered_content}\n---\n"
                            
                            # Extract web search queries
                            if hasattr(candidate.grounding_metadata, 'web_search_queries'):
                                web_search_queries = len(candidate.grounding_metadata.web_search_queries)
                                web_search_content += f"Search queries: {', '.join(candidate.grounding_metadata.web_search_queries)}\n---\n"
                        elif hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                # Look for function calls or tool usage indicators
                                if hasattr(part, 'function_call') or (hasattr(part, 'text') and 'search' in str(part.text).lower()[:200]):
                                    web_search_used = True
                                    web_search_queries = 1  # Assume 1 search query for now
                                    web_search_content += f"Function call or search detected in response\n"
                                    break
            
            # Count tokens on web search content if available
            web_search_tokens = 0
            if web_search_used and web_search_content:
                try:
                    # Use Google's token counting for the search content
                    search_token_response = client.models.count_tokens(
                        model=model_name,
                        contents=web_search_content
                    )
                    web_search_tokens = search_token_response.total_tokens
                except Exception as e:
                    logging.warning(f"Could not count web search tokens: {e}")
                    # Rough estimate: ~1 token per 4 characters
                    web_search_tokens = len(web_search_content) // 4
            
            # Log web search detection
            if web_search_used:
                if web_search_tokens > 0:
                    # Google's API does NOT include grounding tokens in prompt_token_count
                    # We need to add them manually for accurate token counting
                    standard_input_tokens += web_search_tokens
                    logging.info(f"Web search detected: {web_search_queries} queries, {web_search_tokens} grounding tokens added to input")
                    print(f"   🌐 Web search used: {web_search_queries} queries")
                    print(f"   📊 Grounding tokens: {web_search_tokens} (added to input tokens)")
                else:
                    logging.info(f"Web search detected: {web_search_queries} queries")
                    print(f"   🌐 Web search used: {web_search_queries} queries")
                    print(f"   📊 Grounding tokens could not be counted")
            elif not web_search:
                # If web search was disabled but Google still used automatic grounding,
                # we should note this but not count it as intentional web search
                if hasattr(response, 'candidates') and response.candidates:
                    for candidate in response.candidates:
                        if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                            print(f"   ℹ️  Google used automatic grounding (not counted as web search)")
                            break
            
            # Extract clean response text (not response.text which includes metadata)
            clean_response_text = ""
            if hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'text'):
                                clean_response_text += part.text
            
            # Debug logging to understand what we're getting
            logging.info(f"Clean response text extracted: {len(clean_response_text)} characters")
            if hasattr(response, 'text'):
                logging.info(f"Raw response.text length: {len(response.text)} characters")
                logging.info(f"Raw response.text preview: {response.text[:200]}...")
            
            # If we couldn't extract clean text, there's a problem with the response structure
            if not clean_response_text:
                logging.error("Could not extract clean text from Google response")
                logging.error(f"Response structure: {type(response)}")
                if hasattr(response, 'candidates'):
                    logging.error(f"Candidates: {len(response.candidates) if response.candidates else 0}")
                    for i, candidate in enumerate(response.candidates or []):
                        logging.error(f"Candidate {i}: {type(candidate)}")
                        if hasattr(candidate, 'content'):
                            logging.error(f"  Content: {type(candidate.content)}")
                            if hasattr(candidate.content, 'parts'):
                                logging.error(f"  Parts: {len(candidate.content.parts) if candidate.content.parts else 0}")
                
                # Try alternative extraction methods
                if hasattr(response, 'text') and response.text:
                    # If response.text exists but contains metadata, try to clean it
                    raw_text = response.text
                    
                    # Remove common metadata patterns that appear in Google responses
                    # Look for patterns like "SEARCH QUERIES:" and remove everything before the actual content
                    import re
                    
                    # Try to find where the actual content starts after metadata
                    # Common patterns to remove:
                    patterns_to_remove = [
                        r'^.*?SEARCH QUERIES:.*?\n',  # Remove search query metadata
                        r'^.*?WEB SEARCH.*?\n',       # Remove web search metadata
                        r'^.*?GROUNDING.*?\n',        # Remove grounding metadata
                    ]
                    
                    cleaned_text = raw_text
                    for pattern in patterns_to_remove:
                        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
                    
                    # If we removed some metadata, use the cleaned version
                    if len(cleaned_text) < len(raw_text) and cleaned_text.strip():
                        clean_response_text = cleaned_text.strip()
                        logging.info(f"Used cleaned response.text: {len(clean_response_text)} characters")
                    else:
                        # Last resort: use raw text but log the issue
                        clean_response_text = raw_text
                        logging.warning("Using raw response.text as fallback - may contain metadata")
                else:
                    clean_response_text = "No response text found"
            
            return clean_response_text, standard_input_tokens, cached_input_tokens, output_tokens, web_search_used, web_search_content
            
        except Exception as e:
            error_details = str(e)
            logging.error(f"Google API Error: {error_details}")
            # Check for token limit errors and provide more readable message
            if "exceeds maximum input size" in error_details or "exceeds the context size" in error_details:
                return f"ERROR: Token limit exceeded. Please reduce the input size.", 0, 0, 0, False, ""
            return f"ERROR: {error_details}", 0, 0, 0, False, ""
            
    except Exception as e:
        print(f"\n❌ GOOGLE API CALL FAILED")
        print(f"   Error message: {str(e)}")
        print(f"   Model: {model_name}")
        
        logging.error(f"Error asking Google model with model {model_name}: {e}")
        # Re-raise the exception to be caught by the runner
        raise Exception(f"Google API Error: {e}") from e

def calculate_cost(
    model_name: str,
    standard_input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    search_queries: int = 0,
    prompt_size_category: str = "small"  # "small" for <=200k, "large" for >200k
) -> Dict[str, Any]:
    """
    Calculate the cost of using a Google model.
    
    Args:
        model_name: The model to use (e.g., "gemini-2.5-flash-preview-05-20")
        standard_input_tokens: Number of standard input tokens
        cached_input_tokens: Number of cached input tokens
        output_tokens: Number of non-thinking output tokens
        thinking_tokens: Number of thinking output tokens (charged differently)
        search_queries: Number of web search queries
        prompt_size_category: "small" for <=200k tokens, "large" for >200k tokens
        
    Returns:
        Dictionary with cost breakdown
    """
    if model_name not in COSTS:
        return {"error": f"Model {model_name} not found in cost database"}
    
    model_costs = COSTS[model_name]
    
    # Calculate input costs (prices are per 1M tokens)
    if "input_small" in model_costs:  # Pro model with size-based pricing
        input_rate = model_costs[f"input_{prompt_size_category}"]
        cached_rate = model_costs[f"cached_{prompt_size_category}"]
        output_rate = model_costs[f"output_{prompt_size_category}"]
    else:  # Flash model with flat pricing
        input_rate = model_costs["input"]
        cached_rate = model_costs["cached"]
        output_rate = model_costs["output_non_thinking"]
    
    input_cost = (standard_input_tokens * input_rate) / 1_000_000
    cached_cost = (cached_input_tokens * cached_rate) / 1_000_000
    
    # Calculate output costs
    if "output_thinking" in model_costs and thinking_tokens > 0:
        # Flash model with separate thinking token pricing
        output_cost = (output_tokens * model_costs["output_non_thinking"]) / 1_000_000
        thinking_cost = (thinking_tokens * model_costs["output_thinking"]) / 1_000_000
    else:
        # Pro model or no thinking tokens
        output_cost = (output_tokens * output_rate) / 1_000_000
        thinking_cost = 0
    
    # Calculate search costs if applicable
    search_cost = 0
    if search_queries > 0 and "search_cost" in model_costs:
        search_cost = search_queries * model_costs["search_cost"]
    
    total_cost = input_cost + cached_cost + output_cost + thinking_cost + search_cost
    
    return {
        "model": model_name,
        "input_cost": round(input_cost, 6),
        "cached_cost": round(cached_cost, 6),
        "output_cost": round(output_cost, 6),
        "thinking_cost": round(thinking_cost, 6),
        "search_cost": round(search_cost, 6),
        "total_cost": round(total_cost, 6),
        "tokens": {
            "standard_input": standard_input_tokens,
            "cached_input": cached_input_tokens,
            "output": output_tokens,
            "thinking": thinking_tokens,
            "total": standard_input_tokens + cached_input_tokens + output_tokens + thinking_tokens
        }
    }

def count_tokens_google(contents: List, model_name: str) -> int:
    """
    Count tokens for Google models using their count_tokens API.
    
    Args:
        contents: List of content (text and file objects)
        model_name: Google model name
        
    Returns:
        Estimated token count
    """
    try:
        # For files that haven't been uploaded yet, we need to estimate
        estimated_tokens = 0
        actual_contents = []
        
        for item in contents:
            if isinstance(item, str):
                # Text content
                actual_contents.append(item)
            elif hasattr(item, 'name'):
                # Already uploaded file object
                actual_contents.append(item)
            elif isinstance(item, Path):
                # File path - estimate tokens based on file size
                if item.exists():
                    file_size_bytes = item.stat().st_size
                    # Rough estimate: ~1 token per 4 bytes for PDF text content
                    estimated_tokens += file_size_bytes // 4
        
        # Count tokens for actual content if we have any
        if actual_contents:
            response = client.models.count_tokens(
                model=model_name,
                contents=actual_contents
            )
            return response.total_tokens + estimated_tokens
        else:
            return estimated_tokens
            
    except Exception as e:
        logging.warning(f"Error counting tokens for Google model {model_name}: {e}")
        # Return a conservative high estimate if we can't count properly
        return 800000

def get_context_limit_google(model_name: str) -> int:
    """
    Get the context window limit for a Google model.
    
    Args:
        model_name: Google model name
        
    Returns:
        Context window size in tokens
    """
    # All Gemini models currently have ~1M token context windows
    return 1048576

""" imagen model

from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client(api_key='GEMINI_API_KEY')

response = client.models.generate_images(
    model='imagen-3.0-generate-002',
    prompt='Fuzzy bunnies in my kitchen',
    config=types.GenerateImagesConfig(
        number_of_images= 4,
    )
)
for generated_image in response.generated_images:
  image = Image.open(BytesIO(generated_image.image.image_bytes))
  image.show()

"""