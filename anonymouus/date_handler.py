import re
import dateutil.parser

class DateHandler:

    def __init__(self, 
                 replace_invalid_dates: bool = False) -> None:

        # One is adviced to leave 'replace_invalid_dates' set to False to avoid strings
        # that are not actual (malformatted) dates from being replaced.
        self.replace_invalid_dates = replace_invalid_dates
        self.default_patterns = [
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
        self.reset_patterns()
        self.replacements_made = 0
           
    def set_replace_invalid_dates(self, state: bool):
        assert isinstance(state, bool), "set_replace_invalid_dates() expects a boolean"
        self.replace_invalid_dates = state

    def clear_patterns(self):
        self.patterns = []

    def reset_patterns(self):
        self.patterns = self.default_patterns

    def add_pattern(self, pattern: str, replacement: str):
        re.compile(pattern)
        assert isinstance(replacement, str), f"{replacement} is not a string"
        self.patterns.append((pattern, replacement))

    def replace_dates(self, string: str) -> str:
        new_string = string

        for pattern in self.patterns:
            for match in re.finditer(pattern[0], new_string):
                dtstr = new_string[match.span()[0]:match.span()[1]]
                if not self.replace_invalid_dates:
                    try:
                        _ = dateutil.parser.parse(dtstr.replace("_"," "))
                    except Exception:
                        continue

                new_string = new_string[:match.span()[0]] + pattern[1] \
                             + new_string[match.span()[1]:]
                
                self.replacements_made += 1

        return new_string