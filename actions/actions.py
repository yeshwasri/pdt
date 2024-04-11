from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from transformers import pipeline
import requests
from bs4 import BeautifulSoup

class ActionGenerateResponse(Action):
    def name(self) -> str:
        return "action_generate_response"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict) -> list:

        model_name = "distilgpt2"
        generator = pipeline('text-generation', model=model_name)

        user_message = tracker.latest_message.get('text')

        response = generator(user_message, max_length=100, temperature=0.9, top_p=0.85, do_sample=True)[0][
            'generated_text']

        dispatcher.utter_message(text= f"{response}")

        return []

class ActionExtractCredits(Action):
    def name(self) -> str:
        return "action_extract_credits"

    def fetch_credits_online(self, code):
        url = f"https://www.modules.napier.ac.uk/Module.aspx?ID={code}"
        try:
            page = requests.get(url)
            soup = BeautifulSoup(page.content, "html.parser")
            credits_span = soup.find("span", id="ctl00_ContentPlaceHolder1_LBLscqlvalue")
            credits_text = credits_span.get_text().strip() if credits_span else "Credits information not found."
            return credits_text
        except requests.RequestException:
            return "Failed to retrieve data."

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict) -> list:
        subject = next(tracker.get_latest_entity_values('subject'), None)
        if subject:
            subject = subject.lower()
        subject_codes = {
            "software development": "SET07402",
            "web technologies": "SET08220",
            "masters dissertation": "SOC11101",
            "performance studies: integrated musicianship":"MUS07138",
            "civil engineering materials":"CTR07100",
            "computer systems":"CSN07105",

        }

        code = subject_codes.get(subject, None)
        if not code:
            credits_text = "No valid code found for the specified subject."
        else:
            credits_text = self.fetch_credits_online(code)

        dispatcher.utter_message(text=f"Credits for {subject}: {credits_text}")

        return []




class ActionExtractCourseFees(Action):
    def name(self) -> str:
        return "action_extract_course_fees"

    def fetch_fees_online(self, course_url_suffix):
        base_url = "https://www.napier.ac.uk/courses/"
        full_url = f"{base_url}{course_url_suffix}"
        try:
            page = requests.get(full_url)
            soup = BeautifulSoup(page.content, "html.parser")
            fees_info = {}
            table_rows = soup.find_all('tr')
            for row in table_rows:
                region_cell = row.find('td', class_="one")
                fee_cell = row.find('td', class_="two")
                if region_cell and fee_cell:
                    region = region_cell.get_text(strip=True)
                    fee = fee_cell.get_text(strip=True)
                    if fee and fee != '£':
                        fees_info[region] = fee
            return fees_info if fees_info else "No valid fee data found on the page."
        except requests.RequestException as e:
            return f"Failed to retrieve fee information due to: {str(e)}."

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict) -> list:
        course = next(tracker.get_latest_entity_values('fee'), None)
        if course:
            course = course.lower()
        else:
            dispatcher.utter_message(text="Please specify the course you are interested in.")
            return []

        course_dict = {
            "msc computing": "msc-computing-postgraduate-fulltime",
            "msc drug design and biomedical science": "msc-drug-design-and-biomedical-science-postgraduate-fulltime",
            "msc global logistics and supply chain analytics": "msc-global-logistics-and-supply-chain-analytics-postgraduate-fulltime",
        }

        course_url_suffix = course_dict.get(course, None)
        if not course_url_suffix:
            dispatcher.utter_message(text=f"No valid URL found for the specified course: {course}")
            return []

        fee_info = self.fetch_fees_online(course_url_suffix)
        if isinstance(fee_info, str):
            dispatcher.utter_message(text=fee_info)
        else:
            filtered_fees = {k: v for k, v in fee_info.items() if "please note" not in k.lower() and "discount" not in k.lower()}
            fee_message = ", ".join([f"{k}: {v}" for k, v in filtered_fees.items()])
            dispatcher.utter_message(text=f"Fee information for {course}: {fee_message}")
        return []