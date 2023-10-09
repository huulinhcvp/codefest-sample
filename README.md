# GST Codefest 2023 - Legacy

_Stupid bot for the GST Codefest 2023 competition, organized by GST - FPT Software. This repo is only used for reference as well as to test the Server before the official contest takes place._

_This source code is written in the Python 3 programming language._

## Prerequisite

Python 3.9 or later

## Installation

#### 1. Install pipenv using pip
```bash
pip install pipenv
```
#### 2. Move to the /path/to/codefest folder on the cmd/terminal
```bash
cd /path/to/codefest-sample
```
#### 3. Run command
```bash
pipenv shell
```
#### 4. Run command
```bash
pipenv install
```

#### 5. Run bots

1. Change GAME_ID of __player1__ in the __player1/game_info.py__ file.

2. Change GAME_ID of __player2__ in the __player2/game_info.py__ file.

3. Run bot1

```bash
python player1/main.py
```

4. Run bot2 in another process (open a new cmd/terminal window)

```bash
python player2/main.py
```
