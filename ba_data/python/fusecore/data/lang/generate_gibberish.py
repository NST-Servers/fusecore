"""Module to generate gibberish language entries for testing."""

from enum import Enum
import json
import os
from pathlib import Path
import random
import string
from typing import Any

MAIN_PATH = Path(__file__).parent
SOURCE_DIR = Path(MAIN_PATH, "english")
DESTINATION_DIR = Path(MAIN_PATH, "gibberish")


def get_files_from_dir(dir_path: Path) -> list[Path]:
    """Get all language files from a directory.

    Note that this doesn't walk the provided path
    and instead returns the first layer only.
    """
    if not dir_path.exists():
        raise FileNotFoundError(f'path "{dir_path}" does not exist.')
    if not dir_path.is_dir():
        raise TypeError(f'path "{dir_path}" is not dir.')

    lang_files: list[Path] = []
    for dir_file in os.listdir(dir_path):
        file_path = Path(dir_path, dir_file)
        if file_path.suffix == ".json":
            lang_files.append(file_path)
    return lang_files


class ScrambleChoice(Enum):
    """Possible choices our scrambler will take when scanning letters."""

    NONE = 0
    DELETE = 1
    SHUFFLE = 2
    SHUFFLE_ADD = 3
    ADD = 4


def scramble_string(text: str) -> str:
    """Randomize characters in a string following a
    predetermined set of rules closely reassemble
    efro's gibberish generation.
    """
    # attach the seed to the text itself to keep
    # randomization consistent between scrambles.
    salt = "babaubu"
    random.seed(f"{text}{salt}")
    choice_table: dict[ScrambleChoice, int] = {
        ScrambleChoice.NONE: 8,
        ScrambleChoice.DELETE: 7,
        ScrambleChoice.SHUFFLE: 7,
        ScrambleChoice.SHUFFLE_ADD: 3,
        ScrambleChoice.ADD: 3,
    }
    choice_population = list(choice_table.keys())
    choice_weights = list(choice_table.values())

    def is_char_scrambable(char: str) -> bool:
        return not (
            char.isupper()
            or char.isspace()
            or char.isnumeric()
            or char.isdecimal()
            or (char.isascii() and not char.isalpha())
        )

    def rc() -> str:
        return random.choice(((" " + string.ascii_lowercase) * 6) + ".,")

    scrambled_str: str = ""
    # randomize each (allowed) character
    for char in text:
        if not is_char_scrambable(char):
            scrambled_str += char
            continue

        scram_char: str = ""
        choice = random.choices(
            population=choice_population, weights=choice_weights, k=1
        )[0]
        match choice:
            case ScrambleChoice.NONE:
                # pass the char unaffected
                scram_char = char

            case ScrambleChoice.DELETE:
                # don't pass anything
                ...

            case ScrambleChoice.SHUFFLE:
                # return a shuffled character
                scram_char = f"{rc()}"

            case ScrambleChoice.SHUFFLE_ADD:
                # return multiple shuffled characters
                itr = random.randint(2, 3)
                scram_char = "".join([rc() for _ in range(itr)])

            case ScrambleChoice.ADD:
                # return the original and shuffled characters
                itr = random.randint(1, 2)
                scram_char = f"{char}".join([rc() for _ in range(itr)])

        scrambled_str += scram_char

    return scrambled_str


def langfile_to_gibberish(source_file: Path, destination_dir: Path) -> int:
    """Read a '.json' file, convert all entries into gibberish
    and write output into another '.json' file inside the provided dir.

    Returns the amount of lines we've scrambled.
    """
    if source_file.is_dir():
        raise IsADirectoryError(f'source path "{source_file}" is a directory.')
    if not source_file.suffix == ".json":
        raise TypeError(f'source file "{source_file}" is not ".json"')
    if not destination_dir.is_dir():
        raise NotADirectoryError(
            f'destination path "{destination_dir}" is not a directory.'
        )

    file_name = source_file.name
    lang_dict: dict[str, Any] = {}
    # load up all file data
    with open(source_file, "r", encoding="utf-8") as langfile:
        lang_dict = json.loads(langfile.read())

    lines_converted: int = 0

    def scramble_dict(dict_in: dict) -> dict:
        for key, value in dict_in.copy().items():
            match value:
                case dict():  # recursively scramble
                    dict_in[key] = scramble_dict(value)
                case str():  # scramble string
                    dict_in[key] = scramble_string(value)
                case None:  # generate scrambled string from key
                    dict_in[key] = scramble_string(key)
                case _:
                    continue
            nonlocal lines_converted
            lines_converted += 1
        return dict_in

    scrambled_dict = scramble_dict(lang_dict)
    # write scrambled to new file
    output_file = Path(destination_dir, file_name)
    with open(output_file, "w", encoding="utf-8") as gibfile:
        json.dump(scrambled_dict, gibfile, indent=4)

    return lines_converted


if __name__ == "__main__":
    if not SOURCE_DIR.exists() or not SOURCE_DIR.is_dir():
        raise RuntimeError("invalid source path.")
    if not DESTINATION_DIR.exists():
        os.makedirs(DESTINATION_DIR, exist_ok=True)
    elif not DESTINATION_DIR.is_dir():
        raise NotADirectoryError("invalid destination path: not a dir.")

    # automatically generate gibberish.
    source_files = get_files_from_dir(SOURCE_DIR)
    print("generating fusecore gibberish files.")
    for src_file in source_files:
        CNT = langfile_to_gibberish(src_file, DESTINATION_DIR)
        print(
            f'"{src_file.relative_to(MAIN_PATH)}'
            '" > "'
            f'{Path(DESTINATION_DIR, src_file.name).relative_to(MAIN_PATH)}"'
            f" ({CNT} lines)"
        )
