import re
import dateutil.parser

class DateReplacer:

    default_patterns = [
        (r'(\d){4}[-/]{1}(\d){2}[-/]{1}(\d){2}[T\s](\d){2}:(\d){2}:(\d){2}(\.(\d){3})?',
            '1970-01-01T00:00:00'),
        (r'(\d){4}[-/]{1}(\d){2}[-/]{1}(\d){2}', '1970-01-01'),
        (r'(\d){1,2}[-/\\]{1}(\d){1,2}[-/\\]{1}(\d){4}', '01-01-1970'),
        (r'(\d){8}(_?)(\d){4}', '19700101_0000'),
        (r'(\d){8}[T](\d){6}', '19700101T000000'),
        (r'(\d){2}[.]{1}(\d){2}[.]{1}(\d){4}[\s](\d){2}:(\d){2}:(\d){2}',
            '01.01.1970 00:00:00'),
        # (r'(\d){8}(\d){4}', '197001010000'),
    ]

    def __init__(self, replace_invalid_dates: bool = False) -> None:
        # Unless you are really sure of your expressions, leave 'replace_invalid_dates'
        # set to False to avoid strings that only look like malformed dates from
        # being replaced.
        self.set_replace_invalid_dates(replace_invalid_dates)
        self.reset_patterns()
           
    def set_replace_invalid_dates(self, state: bool):
        assert isinstance(state, bool), "set_replace_invalid_dates() expects a boolean"
        self.replace_invalid_dates = state

    def clear_patterns(self):
        self.patterns = []

    def reset_patterns(self):
        self.patterns = self.default_patterns

    def add_pattern(self, pattern: str, replacement: str):
        re.compile(pattern)
        assert isinstance(replacement, str) or callable(replacement), \
            f"{replacement} is not a string or a function"
        self.patterns.append((pattern, replacement))

    def replace(self, string: str) -> str:
        new_string = string

        for pattern, replacement in self.patterns:
            for match in re.finditer(pattern, new_string):
                datestr = new_string[match.span()[0]:match.span()[1]]
                if not self.replace_invalid_dates:
                    try:
                        _ = dateutil.parser.parse(datestr.replace("_"," "))
                    except Exception:
                        continue

                new_string = "".join([new_string[:match.span()[0]],
                                      replacement(datestr) if  callable(replacement) else replacement,
                                      new_string[match.span()[1]:]])

        return new_string