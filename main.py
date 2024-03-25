import atexit
import json
import os
import pickle
import random
import time
import tkinter as tk

import pyautogui
from selenium import webdriver
from selenium.common import NoSuchElementException, TimeoutException, StaleElementReferenceException, \
    ElementClickInterceptedException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

from models import *

AWAIT_INPUT = "yellow"
AWAIT_CLICK = "orange"
WAITING = "aqua"
DORMANT = "white"
COOKIES_PATH = 'cookies.pkl'

NEED_ANSWER_COLOR = 'rgb(250, 129, 49)'
OKAY_ANSWER_COLOR = 'rgba(121, 185, 51, 0.9)'


def wrap_in_challenge_color(color):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            self.set_challenge_color(color)
            result = func(self, *args, **kwargs)
            self.set_challenge_color()
            return result

        return wrapper

    return decorator


class Status:
    _WIDTH = 350
    _HEIGHT = 55
    _CLICK_STATUS = " (Click ME to continue)"

    def __init__(self, additional_status_proccessing=None):
        self._status = ""
        self._color = ""
        self._clicked = False
        self._additional_status_proccessing = additional_status_proccessing

        self._root = tk.Tk()
        self._root.withdraw()

        self._status_window = tk.Toplevel(self._root)
        self._status_window.title("-")
        self._status_window.geometry(f"{self._WIDTH}x{self._HEIGHT}")
        self._status_window.attributes("-topmost", True)
        self._status_window.attributes('-alpha', 0.3)
        self._status_window.overrideredirect(True)

        screen_width = self._root.winfo_screenwidth()
        self._status_window.geometry(f"+{screen_width - self._WIDTH}+0")

        # Label to display status
        self._status_label = tk.Label(self._status_window, textvariable=self._status, wraplength=self._WIDTH - 10)
        self._status_label.place(relx=0.5, rely=0.5, anchor='center')
        self._status_window.bind('<Button-1>', self._on_click)

        atexit.register(self._exit)
        self.color = DORMANT

    def _on_click(self, event):
        self._clicked = True

    @property
    def color(self):
        return self._color

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value
        if self._additional_status_proccessing is not None:
            self._status = self._additional_status_proccessing(self._status)

        self._status_label.config(text=self._status)
        self._status_window.update()

    @color.setter
    def color(self, value):
        self._color = value
        self._status_window.config(bg=self._color)
        self._status_window.update()

    @staticmethod
    def _focus():
        pyautogui.hotkey('alt', 'tab')

    def wait_to_be_clicked(self, after=None):
        self._clicked = False
        old_color = self.color
        self.color = AWAIT_CLICK
        self.status += self._CLICK_STATUS

        while not self._clicked:
            self._root.update()

        self.color = old_color
        self.status = self.status[:-len(self._CLICK_STATUS)]
        self._clicked = False
        self._focus()
        if after is not None:
            after()

    def _exit(self):
        self._root.destroy()


class Duolingo:
    def __init__(self):
        self._hearts = -1
        self.status = Status(self.additional_status_proccessing)

        self.status.status = "PREVIEW"
        time.sleep(3)

        self.status.status = "Launching Browser..."

        options = Options()
        options.add_argument("--mute-audio")

        self.driver = webdriver.Chrome(options=options)

        atexit.register(self.driver.close)

    def additional_status_proccessing(self, status: str):
        if status.startswith("❤"):
            status = status.split(" ", 1)[1]
        return f"❤{self.heart_count} {status}"

    def open(self):
        self.status.status = "Opening Duolingo"
        self.redirect("https://www.duolingo.com")

        if os.path.exists(COOKIES_PATH):
            self.status.status = "Loading cookies..."
            with open(COOKIES_PATH, 'rb') as file:
                cookies = pickle.load(file)
            for cookie in cookies:
                self.status.status = f"Adding cookie: {cookie['name']}"
                self.driver.add_cookie(cookie)

            self.refresh()

        self.status.status = "Opened Duolingo"

    @property
    def title(self):
        try:
            return self.driver.title
        except:
            return ""

    def refresh(self):
        self.status.status = "Refreshing..."
        self.driver.refresh()

        while "Duolingo" not in self.title:
            pass

        self.driver.fullscreen_window()

        self.status.status = "Refreshed!"

    def redirect(self, url):
        self.status.status = f"Redirecting..."
        self.driver.get(url)

        while "Duolingo" not in self.title:
            pass

        try:
            self.driver.fullscreen_window()
        except:
            pass

    def accept_cookies(self):
        try:
            self.status.status = "Accepting cookies..."
            button = self.driver.find_element(value="onetrust-accept-btn-handler")
            button.click()
            self.status.status = "Accepted cookies!"
        except NoSuchElementException:
            self.status.status = "Couldn't accept cookies"

    @property
    def logged_in(self):
        return any(cookie.get('name') == 'jwt_token' for cookie in self.driver.get_cookies())

    def _get_challenge_container(self):
        challenge_header = self._get_challenge_header_element()
        if challenge_header is None:
            return None
        try:
            return challenge_header.find_element(By.XPATH, '../../..')
        except (NoSuchElementException, StaleElementReferenceException):
            return None

    def _get_hearts_from_page(self):
        try:
            return int(self.driver.find_element(by=By.CSS_SELECTOR, value='[src*="hearts"]')
                       .find_element(by=By.XPATH, value='./following-sibling::span').text)
        except:
            return None

    @property
    def heart_count(self):
        if (hearts := self._get_hearts_from_page()) is not None:
            self._hearts = hearts
            return hearts
        return self._hearts

    @property
    def challenge_type(self):
        return self._get_challenge_container().get_attribute('data-test').rsplit()[-1]

    def set_challenge_color(self, color: str = 'cadetblue', question_container=None):
        if question_container is None:
            question_container = self.challenge_container
        self.driver.execute_script(f"""
                    let question_container = document.getElementsByClassName("{question_container.get_attribute('class')}")[0];
                    question_container.setAttribute('modified', '');
                    question_container.style.backgroundColor = '{color}';
                    question_container.style.borderRadius = '10px';
                """)

    @property
    def challenge_container(self):
        root_container = self._get_challenge_container()
        main_container = root_container.find_element(by=By.TAG_NAME, value="div")
        question_container = main_container.find_element(by=By.XPATH, value="./child::*[2]")
        if question_container.get_attribute('modified') is None:
            self.set_challenge_color(question_container=question_container)

        return question_container

    def _get_challenge_header_element(self):
        try:
            return self.driver.find_element(By.CSS_SELECTOR, '[data-test="challenge-header"]')
        except NoSuchElementException:
            return None

    @property
    def challenge_header_text(self):
        challenge_header = self._get_challenge_header_element()
        if challenge_header is None:
            return None
        return challenge_header.find_element(By.TAG_NAME, value="span").text

    @property
    def in_practice(self):
        return self._get_challenge_container() is not None and not (self._get_hearts_from_page() == 0)

    def _get_child(self, element, index):
        return element.find_element(By.XPATH, f'./child::*[{index + 1}]')

    @property
    def question_container(self):
        return self._get_child(self.challenge_container, 0)

    @property
    def answer_container(self):
        return self._get_child(self.challenge_container, 1)

    def login(self):
        if self.logged_in:
            self._login()
            return
        self.status.status = "Logging in..."
        try:
            login_button = self.driver.find_element(By.CSS_SELECTOR, '[data-test="have-account"]')
            login_button.click()
        except NoSuchElementException:
            pass
        self.status.status = "Please login to Duolingo"
        self.status.color = AWAIT_INPUT

        while not self.logged_in:
            time.sleep(1)
        self._login()

    def _login(self):
        self.status.status = "Logged in!"
        self.status.color = DORMANT
        self.driver.fullscreen_window()

    def accept_consent(self):
        try:
            self.status.status = "Waiting for consent dialog..."
            self.status.color = WAITING
            WebDriverWait(self.driver, 10).until(lambda x: x.find_element(By.CLASS_NAME, "fc-dialog-content"))
        except TimeoutException:
            self.status.status = "No consent dialog... skipping"
            return
        finally:
            self.status.color = DORMANT

        try:
            self.status.status = "Accepting consent..."
            button = self.driver.find_element(by=By.CLASS_NAME, value="fc-cta-consent")
            button.click()
            self.status.status = "Accepted consent!"
        except NoSuchElementException:
            self.status.status = "Couldn't accept consent"

        with open(COOKIES_PATH, 'wb') as file:
            pickle.dump(self.driver.get_cookies(), file)

    def _start_practice(self):
        if "https://www.duolingo.com/learn" not in self.driver.current_url:
            try:
                self.press_next()
            except:
                pass
            if self.heart_count < 1:
                self.attempt_exit_no_heart()
            self.status.status = "Double checking practice..."
            time.sleep(3)
            if self.in_practice:
                return True
            self.status.status = "Navigating to learn page..."
            self.redirect("https://www.duolingo.com/learn")

        self.status.status = "Starting practice..."
        practice_menu = self.driver.find_element(By.CSS_SELECTOR, '[data-test="hearts-menu"]')
        hover_action = ActionChains(self.driver).move_to_element(practice_menu)
        hover_action.perform()
        self.status.status = "Hovered over practice menu"

        try:
            practice_menu_text = self.driver.find_element(By.XPATH, '//*[text()="Practice to earn hearts"]')
            practice_button = practice_menu_text.find_element(By.XPATH, 'ancestor::button')
            practice_button.click()
        except NoSuchElementException:
            return self._start_practice()

        return False

    def start_practice(self):
        attempt = 0
        while not self.in_practice:
            attempt += 1
            if attempt > 3 or self.heart_count >= 5:
                self.status.status = "Couldn't start practice, doing a lesson instead..."
                time.sleep(.1)
                self.status.color = DORMANT
                self.redirect("https://www.duolingo.com/lesson/unit/1/level/1")
            try:
                if attempt > 4 or self.heart_count >= 5 or not self._start_practice():
                    for i in range(60):
                        self.status.status = f"Confirming practice... [{attempt}] ({i * .1:.1f}/6)"
                        self.status.color = WAITING
                        time.sleep(.1)
            except:
                attempt = 0

        self.status.status = "Started practice!"
        self.status.color = DORMANT

    def _get_text(self, element):
        texts = element.find_elements(By.XPATH, ".//*[@lang]")
        return ''.join([text.text for text in texts if
                        text.get_attribute('lang') in ('en', 'ja') and not text.find_elements(By.TAG_NAME, 'ruby') and not text.find_elements(By.XPATH, ".//*[@lang]")])

    def fetch_question(self):
        question_container = self.question_container
        return self._get_text(question_container)

    def assist_fetch_options(self):
        choices = self.challenge_container.find_elements(By.CSS_SELECTOR, '[data-test="challenge-choice"]')
        return choices, [
            self._get_text(
                self._get_child(self._get_child(choice, 1), 0)
            )
            for choice in choices
        ]

    def select_fetch_options(self):
        choices = self.challenge_container.find_elements(By.CSS_SELECTOR, '[data-test="challenge-choice"]')
        return choices, [
            self._get_text(
                self._get_child(choice, 1)
            )
            for choice in choices
        ]

    def _translate_get_text_of_part(self, part):
        text_obj = self._get_child(
            self._get_child(self._get_child(self._get_child(part, 0), 0), 1), 0)
        if '\n' not in text_obj.text:
            return text_obj.text
        else:
            return self._get_text(text_obj)

    def translate_fetch_parts(self):
        parts = self.answer_container.find_element(
            By.CSS_SELECTOR, '[data-test="word-bank"]'
        ).find_elements(By.TAG_NAME, 'div')

        return parts, [
            self._translate_get_text_of_part(part)
            for part in parts
        ]

    def get_challenge_info(self):
        self.status.status = "Getting challenge info..."
        info = {
            "header": self.challenge_header_text,
            "type": self.challenge_type,
        }

        if info["type"] in ["challenge-assist", "challenge-translate"]:
            info["question"] = self.fetch_question()

        if info["type"] == "challenge-assist":
            info["_options"], info["options"] = self.assist_fetch_options()
        elif info["type"] == "challenge-translate":
            info["_parts"], info["parts"] = self.translate_fetch_parts()
        elif info["type"] == "challenge-select":
            info["_options"], info["options"] = self.select_fetch_options()
            info["type"] = "challenge-assist"

        self.status.status = "Got challenge info!"
        return info

    @wrap_in_challenge_color(NEED_ANSWER_COLOR)
    def get_answer(self, info):
        self.status.status = "Please provide answer"
        self.status.color = AWAIT_INPUT

        if info["type"] == "challenge-assist":
            options = info["_options"]

            while True:
                for i, option in enumerate(options):
                    if option.get_attribute('aria-checked') == 'true':
                        self.status.status = f"User chose answer {i + 1}!"
                        self.status.color = DORMANT
                        time.sleep(1)
                        return QuestionAnswer(question=info["question"], answer=info["options"][i])
        elif info["type"] == "challenge-translate":
            self.status.wait_to_be_clicked()

            answer_parts = self._get_child(self._get_child(self._get_child(self._get_child(
                self._get_child(self._get_child(self.answer_container, 0), 0),
                0), 0), 0), 1).find_elements(By.TAG_NAME, 'div')

            answer = ' '.join([self._translate_get_text_of_part(part) for part in answer_parts])

            return QuestionAnswer(question=info["question"], answer=answer)

    def press_next(self):
        self.status.status = "Continuing..."
        self.status.color = WAITING
        next_button = self.driver.find_element(By.CSS_SELECTOR, '[data-test="player-next"]')
        next_button.click()
        time.sleep(1)
        next_button.click()
        self.status.status = "OK!"
        self.status.color = DORMANT

    def press_skip(self):
        self.status.status = "Skipping..."
        skip_button = self.driver.find_element(By.CSS_SELECTOR, '[data-test="player-skip"]')
        skip_button.click()
        self.status.status = "Skipped!"

    def _need_new_answer(self, session, info):
        answer = self.get_answer(info)
        if answer is None:
            return False
        session.add(answer)
        session.commit()
        self.status.status = f"Answer saved: {answer.answer}"
        time.sleep(1)
        return True

    def try_answer(self, session, info, answer):
        if info["type"] == "challenge-assist":
            index = info["options"].index(answer.answer)
            info['_options'][index].click()
        elif info["type"] == "challenge-translate":
            text = answer.answer
            used = []
            while text:
                for i, part in sorted(enumerate(info["parts"]), key=lambda x: len(x[1]), reverse=True):
                    if i not in used and text.startswith(part):
                        text = text[len(part):].strip()
                        info["_parts"][i].click()
                        time.sleep(.2)
                        used.append(i)
                        break
                else:
                    return 0
        return True

    def attempt_exit_no_heart(self):
        try:
            self.driver.find_element(By.XPATH,
                                     '//span[text()="No thanks"]/..').click()
        except:
            pass
        try:
            self.driver.find_element(By.CSS_SELECTOR,
                                     '[data-test="notification-drawer-no-thanks-button"]').click()
        except:
            pass

    def solve_challenge(self, info):
        if not info.get('question', 1):
            self.status.status = "ERROR, couldn't get question!"
            self.set_challenge_color(NEED_ANSWER_COLOR)
            return False

        if self._get_hearts_from_page() is not None:
            self.status.status = "LESSON MODE"

            if info["type"] == "challenge-listenTap":
                self.press_skip()
            elif info["type"] == "challenge-translate":
                for part in info["_parts"]:
                    part.click()
            elif info["type"] == "challenge-assist":
                random.choice(info["_options"]).click()
            else:
                return False
            self.attempt_exit_no_heart()
            return True

        with Session() as session:
            if info["type"] in ["challenge-assist", "challenge-translate"]:
                answers = session.query(QuestionAnswer).filter(QuestionAnswer.question == info["question"]).all()
                if len(answers) < 1:
                    return self._need_new_answer(session, info)
            elif info["type"] == "challenge-listenTap":
                self.press_skip()
                return True
            else:
                return False

            self.set_challenge_color(OKAY_ANSWER_COLOR)

            for answer in answers:
                result = self.try_answer(session, info, answer)
                if type(result) == bool:
                    return result

            return self._need_new_answer(session, info)


if __name__ == "__main__":
    duolingo = Duolingo()

    duolingo.open()

    duolingo.accept_cookies()
    duolingo.login()
    duolingo.accept_consent()

    while duolingo.logged_in:
        duolingo.start_practice()

        while duolingo.in_practice:
            try:
                temp_info = duolingo.get_challenge_info()
            except:
                break
            print(temp_info)

            try:
                if not duolingo.solve_challenge(temp_info):
                    duolingo.status.wait_to_be_clicked()
                duolingo.press_next()
                time.sleep(2)
            except ElementClickInterceptedException:
                pass
