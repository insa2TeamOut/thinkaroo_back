import os
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
import uvicorn
import openai
import logging
import json
import re
import base64

# GPT-4 API 키 설정
openai.api_key = ""
app = FastAPI()
logging.basicConfig(level="DEBUG")


@app.post("/make_quiz.openai.azure.com/")
async def make_quiz(difficulty: str = Form(...), subject: str = Form(...), content: str = Form(...)):
    try:
        gpt_response_quiz = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "user", "content": "과목이 " + subject + "에서"
                                            + difficulty + "의 수준으로 " + content + " 이 개념이 중점인 문제를 하나 만들어줘."
                                            + " 결과는 반드시 한국어로 나오게 해야해"
                 },
            ],
            max_tokens=4000,
            presence_penalty=0,
            frequency_penalty=0,
            temperature=1,
        )

        rtn_answer = re.sub(r'\\n\d+|\\n[a-zA-Z]', '', gpt_response_quiz.choices[0].message.content)

        return rtn_answer
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/check_answer.openai.azure.com/")
async def evaluate_solution(file: UploadFile = File(...), text: str = Form(...)):
    try:

        UPLOAD_DIR = "./img"
        image_data = await file.read()
        filename = f"{str(uuid.uuid4())}.jpg"  # uuid로 유니크한 파일명으로 변경

        # 이미지 저장
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(os.path.join(UPLOAD_DIR, filename), "wb") as fp:
            fp.write(image_data)
        logging.info("업로드 완료")
        logging.info("업로드 파일 : " + filename)

        def encode_image(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')

        image_path = "./img/" + filename
        base64_image = encode_image(image_path)

        # GPT-4 API 첫 번째 함수 호출
        gpt_response_editing = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "user", "content": text},
                {"role": "system",
                 "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpg;base64,{base64_image}"}}]},
                {"role": "system", "content": "문제의 해설을 이용하여 이미지의 해설을 첨삭 해줘. 첨삭의 결과는 반드시 한국어야 만해."}
            ],
            max_tokens=4000,
            presence_penalty=0,
            frequency_penalty=0,
            temperature=1,
        )

        # GPT-4 API 두 번째 함수 호출
        gpt_response_choice_answer = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "user", "content": text},
                {"role": "system",
                 "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpg;base64,{base64_image}"}}]},
                {"role": "system", "content": "문제의 정답과 이미지의 답을 비교하여 맞는지 확인 해줘."}
            ],
            functions=[
                {
                    "name": "choice_answer",
                    "description": "이미지에서 사용자의 정답이 문제의 정답과 같은지 비교합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "recommend": {
                                "type": "array",
                                "description": "이미지에서 사용자의 정답이 문제의 정답과 같은지 비교합니다.",
                                "items": {
                                    "type": "string",
                                    "enum": ["X", "O"],
                                },
                                "minItems": 1,
                                "maxItems": 1,
                            },
                        }
                    }
                }
            ],
            function_call={"name": "choice_answer"},
            max_tokens=4000,
            presence_penalty=0,
            frequency_penalty=0,
            temperature=1,
        )

        returnCheck = "O"
        json_string = gpt_response_choice_answer.choices[0].message.function_call.arguments
        data = json.loads(json_string)
        if "X" in data.get("recommend", []):
            returnCheck = "X"

        os.remove("./img/" + filename)
        logging.info(filename)

        # 결과 반환
        return {
            "filename": filename,
            "editing_result": gpt_response_editing.choices[0].message.content,
            "choice_answer_result": returnCheck
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
