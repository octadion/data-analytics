from pandasai.prompts import AbstractPrompt
from pandasai import Agent
from pandasai.responses.response_parser import ResponseParser
from pandasai.helpers.query_exec_tracker import QueryExecTracker, ResponseType
from typing import Union, Optional
import base64


class MyQueryExecTracker(QueryExecTracker):

    def __init__(
            self,
            server_config: Union[dict, None] = None,
    ) -> None:
        super().__init__(server_config)

    def _format_response(self, result: ResponseType) -> ResponseType:

        if result["type"] == "dataframe":
            df_dict = self.convert_dataframe_to_dict(result["value"])
            return {"type": result["type"], "value": df_dict}

        elif result["type"] == "plot":
            if isinstance(result["value"], str):
                return {
                    "type": 'string',
                    "value": result["value"],
                }
            with open(result["value"], "rb") as image_file:
                image_data = image_file.read()
            base64_image = (
                f"data:image/png;base64,{base64.b64encode(image_data).decode()}"
            )
            return {
                "type": result["type"],
                "value": base64_image,
            }
        else:
            return result


class MyResponseParser(ResponseParser):

    def __init__(self, context) -> None:
        super().__init__(context)
    def format_plot(self, result: dict):
        return result["value"]


class MyCorrectErrorPrompt(AbstractPrompt):

    @property
    def template(self) -> str:
        prompt = '''
{dataframes}

The user asked the following question:
{conversation}

You generated this python code:
{code}

It fails with the following error:
{error_returned}

Fix the python code above and return the new python code:
If there is an error 'File name too long: '<!DOCTYPE html>', help me change the type of 'result' to string
If there is an error 'Can only use .dt accessor', please convert the processing column to datetime type before the logic
If there is an error 'All objects passed were None', please refer or use the initial code that has been generated.
        '''
        return prompt

    def set_var(self, var, value):
        if self._args is None:
            self._args = {}
        if var == "dfs":
            self._args["dataframes"] = self._generate_dataframes(value)
        if var == "error_returned":
            print('error', value)
            self._args["error_returned"] = str(value)[:1000]
        else:
            self._args[var] = value


class MyReasoningPrompt(AbstractPrompt):
    """The simple reasoning instructions"""

    @property
    def template(self) -> str:
        prompt = '''
At the end, declare "result" var dict: {output_type_hint}
{viz_library_type}
{instructions}

Generate python code and return full updated code:        
        '''
        return prompt


class MyGeneratePythonCodePrompt(AbstractPrompt):
    """Prompt to generate Python code"""

    @property
    def template(self) -> str:
        prompt = '''
{dataframes}
{skills}

{prev_conversation}

{code_description}
```python
{current_code}
```

{last_message}
Variable `dfs: list[pd.DataFrame]` is already declared.
{reasoning}
            '''
        return prompt

    def setup(self, **kwargs) -> None:
        if "custom_instructions" in kwargs:
            self.set_var("instructions", kwargs["custom_instructions"])
        else:
            self.set_var("instructions", "")

        if "current_code" in kwargs:
            self.set_var("current_code", kwargs["current_code"])
        else:
            self.set_var("current_code", MyCorrectErrorPrompt(dfs_declared=True))

        if "code_description" in kwargs:
            self.set_var("code_description", kwargs["code_description"])
        else:
            self.set_var("code_description", "Update this initial code:")

        if "last_message" in kwargs:
            self.set_var("last_message", kwargs["last_message"])
        else:
            self.set_var("last_message", "")

        if "prev_conversation" in kwargs:
            self.set_var("prev_conversation", kwargs["prev_conversation"])
        else:
            self.set_var("prev_conversation", "")

    def on_prompt_generation(self) -> None:
        default_import = "import pandas as pd"
        engine_df_name = "pd.DataFrame"

        self.set_var("default_import", default_import)
        self.set_var("engine_df_name", engine_df_name)
        self.set_var("reasoning", MyReasoningPrompt())


class MyExplainPrompt(AbstractPrompt):
    """Prompt to explain code generation by the LLM"""

    @property
    def template(self) -> str:
        prompt = '''
        The previous conversation we had

        <Conversation>
        {conversation}
        </Conversation>

        Based on the last conversation you generated the following code:

        <Code>
        {code}
        </Code>

        Explain how you came up with code for non-technical people without 
        mentioning technical details or mentioning the libraries used?
        Use Indonesian language for explanation.
        '''
        return prompt

    def setup(self, conversation: str, code: str) -> None:
        self.set_var("conversation", conversation)
        self.set_var("code", code)


class MyPandasAgent(Agent):

    def chat(self, query: str, output_type: Optional[str] = None):
        try:
            is_related = self.check_if_related_to_conversation(query)
            self._lake.is_related_query(is_related)
            self._lake._query_exec_tracker = MyQueryExecTracker(
                server_config=self._lake._config.log_server,
            )
            return self._lake.chat(query, output_type=output_type)
        except Exception as exception:
            return (
                "Unfortunately, I was not able to get your answers, "
                "because of the following error:\n"
                f"\n{exception}\n"
            )

    def explain(self) -> str:
        """
        Returns the explanation of the code how it reached to the solution
        """
        try:
            prompt = MyExplainPrompt(
                conversation=self._lake._memory.get_conversation(),
                code=self._lake.last_code_executed,
            )
            response = self._call_llm_with_prompt(prompt)
            self._logger.log(
                f"""Explanation:  {response}
                """
            )
            return response
        except Exception as exception:
            return (
                "Unfortunately, I was not able to explain, "
                "because of the following error:\n"
                f"\n{exception}\n"
            )