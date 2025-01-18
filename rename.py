from openai import OpenAI

import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("API_KEY is not set in the environment variables")

client = OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key=OPENAI_API_KEY,
    base_url="https://api.chatanywhere.cn/v1"
)


def gpt_35_api(prompt):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def mp3_rename(message):
    prompt = '识别以下文本中的歌名和歌手，忽略其他内容，按照‘歌名 - 歌手’格式输出, 如果有两个歌手则按照‘歌名 - 歌手1&歌手2’格式输出，-两侧有空格，&两侧没有空格，输出文字全部转换成简体中文：'
    message = prompt + message
    return gpt_35_api(message)


if __name__ == '__main__':
    message = '這是你期盼的長大嗎 (張齊山ZQS) Cover ( 蔡恩雨 Priscilla Abby)'
    print(mp3_rename(message))
