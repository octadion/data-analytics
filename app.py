import streamlit as st
from pandasai.connectors import PostgreSQLConnector
from pandasai import SmartDataframe, SmartDatalake
from pandasai.llm import OpenAI
import pandas as pd
from pandasai import Agent
from pandasai.responses import StreamlitResponse
import os
from PIL import Image
# from langchain.llms import LlamaCpp
import psycopg2
from pandasai.prompts import AbstractPrompt
from agent import MyPandasAgent, MyCorrectErrorPrompt, MyResponseParser
from utils import gen_json_response
from pandasai.helpers.openai_info import get_openai_callback
from dotenv import load_dotenv

load_dotenv()

llm = OpenAI(api_token="")
user = os.getenv('DB_USER')
password = os.getenv('DB_PASS')
host = os.getenv('DB_HOST')
port = os.getenv('DB_PORT')
database = os.getenv('DB_NAME')
sslmode = os.getenv('DB_SSLMODE')

conn = psycopg2.connect(
    dbname=database,
    user=user,
    password=password,
    host=host,
    port=port
)

def parse_output(result, last_code, explanation):
    '''
    Parse the return result Based on the above explanation
    '''
    res_data = {
        'text': '',
        'data': [],
        'html': '',
    }
    result_text = f"""
{explanation}
I generated the following code and executed it:

```python
{last_code}
```

The final result is as follows:

"""
    if isinstance(result, str):
        if '<!DOCTYPE html>' in result:
            res_data['html'] = result
        else:
            result_text += str(result)
    if isinstance(result, SmartDataframe):
        df = result.dataframe
        df.fillna("", inplace=True)
        data_li = df.to_dict(orient='records')
        res_data['data'] = data_li
    res_data['text'] = result_text
    return gen_json_response(data=res_data)

OUTPUT_GPAPH_FOLDER = '.exports_charts$$/'

def init_graph_folder():
    if not os.path.isdir(OUTPUT_GPAPH_FOLDER):
        os.makedirs(OUTPUT_GPAPH_FOLDER)
        
def main():
    st.title('Data - Analytics')

    mode = st.selectbox('Pilih Mode Input Data:', ('SQL', 'CSV'))

    if mode == 'SQL':
        st.subheader('SQL')
        dataframe = pd.read_sql('SELECT * FROM komunitas_anggota_jatim.anggota', conn)
        conn.close()

        init_graph_folder()
        st.session_state
        if "data_objects" not in st.session_state:
            st.session_state.data_objects = []
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        for message in st.session_state.messages:
            with st.chat_message(message["question"]):
                st.markdown(message["answer"])
                for data_object in st.session_state.data_objects:
                    if data_object["message"] == message:
                        if isinstance(data_object["data"], str) and OUTPUT_GPAPH_FOLDER in data_object["data"]:
                            st.image(data_object["data"])
        with open('Deskripsi Kolom.txt', 'r') as file:
            metadata = file.read()
        if prompt := st.chat_input("Ask me about data..."):
            st.session_state.messages.append({"question":"user","answer":prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                # change to MyPandasAgent if want to use multi table conversation (less acc so far)
                # description="Deskripsi kolom: domisili_kota_kabupaten = nama kota atau kabupaten anggota komunitas tinggal, kota = kota atau kabupaten sekolah berada, kualifikasi = kualifikasi pendidikan terakhir anggota komunitas",
                df = SmartDataframe(dataframe, description=metadata,
                                   config={"llm": llm, "save_charts_path": OUTPUT_GPAPH_FOLDER,
                    "save_charts": True,                   
                    # "response_parser": StreamlitResponse,
                    "enable_cache": False,
                    # "enforce_privacy": True,
                    "custom_whitelisted_dependencies": ["pyecharts"],
                    "custom_prompts": {
                        "correct_error": MyCorrectErrorPrompt(),},
                        "response_parser": MyResponseParser
                    })
                # "6. if the question is related to a previous question, relate the answer to the context of the previous question-answer.\n" \
                
                question_prompt = "Before answering the question, the following requirements apply to the answer format:\n" \
                    "1. If it's not returning data, please answer the corresponding question in Bahasa Indonesia.\n" \
                    "2. Always define and load the dataframe first.\n" \
                    "3. Interpret the prompt first, then adjust it to the existing metadata dataframes.\n" \
                    "4. When generating code, keep using the original data and do not use mock data. When filtering data, ALWAYS USE the LIKE method or str.contains, DONT USE exact match.\n" \
                    "5. If the question is related to drawing, always save the plots and use the saved plots.\n" \
                    "Based on the above requirements, please answer the following question:\n"
                question = f"{question_prompt}{prompt}"
                with get_openai_callback() as cb:
                    answer = df.chat(question)
                    # print(cb)
                    last_code = df.last_code_executed
                    # explanation = df.explain()
                    last_prompt = df.last_prompt
                    print(last_prompt)
                # response = parse_output(answer, last_code, explanation)
                # print(response)
                message_placeholder = st.empty()
                if isinstance(answer, (SmartDataframe, pd.DataFrame, pd.Series)):
                    message_placeholder.dataframe(answer, use_container_width= True, hide_index= True)
                    # st.session_state.data_objects.append({"message": {"question":"assistant", "answer":answer}, "data": answer})
                elif isinstance(answer, str):
                    if OUTPUT_GPAPH_FOLDER in answer:
                        print(answer)
                        if os.path.exists(answer):
                            st.image(answer)
                            # os.remove(answer)
                            st.session_state.data_objects.append({"message": {"question":"assistant", "answer":answer}, "data": answer})
                    else:
                        message_placeholder.markdown(answer, unsafe_allow_html=True)
                else:
                    message_placeholder.markdown(answer, unsafe_allow_html=True)
                st.session_state.messages.append({"question":"assistant", "answer":answer})

    else:
        st.subheader('CSV')
        file_input = None
        file_input = st.file_uploader("Upload files for analysis", type=["csv","xlsx"], accept_multiple_files=True)
        init_graph_folder()
        if file_input:
            st.success('Successfully uploaded!', icon="✅")
            if "files" not in st.session_state:
                st.session_state.files = []
            for file_name in file_input:
                data_file_temp = pd.read_csv(file_name, error_bad_lines=False)
                st.session_state.files.append(data_file_temp)
            st.session_state
            if "data_objects" not in st.session_state:
                st.session_state.data_objects = []
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            for message in st.session_state.messages:
                with st.chat_message(message["question"]):
                    st.markdown(message["answer"])
                    for data_object in st.session_state.data_objects:
                        if data_object["message"] == message:
                            if isinstance(data_object["data"], str) and OUTPUT_GPAPH_FOLDER in data_object["data"]:
                                st.image(data_object["data"])
            if prompt := st.chat_input("Ask me about data..."):
                st.session_state.messages.append({"question":"user","answer":prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    df = SmartDatalake(st.session_state.files, config={"llm": llm, "save_charts_path": OUTPUT_GPAPH_FOLDER,
                    "save_charts": True,                   
                    # "response_parser": StreamlitResponse,
                    "enable_cache": False,
                    # "enforce_privacy": True,
                    "custom_whitelisted_dependencies": ["pyecharts"],
                    "custom_prompts": {
                        "correct_error": MyCorrectErrorPrompt(),},
                        "response_parser": MyResponseParser
                    })
                    answer = df.chat(prompt)
                    message_placeholder = st.empty()
                    if isinstance(answer, (SmartDataframe, pd.DataFrame, pd.Series)):
                        message_placeholder.dataframe(answer, use_container_width= True, hide_index= True)
                    elif isinstance(answer, str):
                        if OUTPUT_GPAPH_FOLDER in answer:
                            print(answer)
                            if os.path.exists(answer):
                                st.image(answer)
                                os.remove(answer)
                        else:
                            message_placeholder.markdown(answer, unsafe_allow_html=True)
                    else:
                        message_placeholder.markdown(answer, unsafe_allow_html=True)
                    st.session_state.messages.append({"question":"assistant", "answer":answer})
                    
if __name__ == "__main__":
    main()
