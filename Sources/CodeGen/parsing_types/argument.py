from ast import Set
from typing import List, Dict
from os.path import abspath
from jinja2 import Template

from utils import camel_case, snake_case, THIS_DIR
from config import names_to_substitute, token_to_substitute, arguments_to_ignore

ARG_TYPES = {
    "string": "String",
    "integer": "Int",
    "double": "Double",
    "key": "String",
    "pattern": "String",
    "unix-time": "Int64",
    "pure-token": "token",
    "oneof": "oneof",
    "block": "block",
}

TEST_VALUES = {
    "String": '"TestString"',
    "Int": "123",
    "Double": "123.0",
    "Int64": "123",
}

with open(abspath(f"{THIS_DIR}/templates/parameter.swift")) as file:
    parameter_template = Template(file.read())

with open(abspath(f"{THIS_DIR}/templates/test_parameter.swift")) as file:
    test_parameter_template = Template(file.read())


class Argument(object):
    def __init__(self, desc: Dict):
        self.name: str = names_to_substitute.get(
            camel_case(desc["name"]), camel_case(desc["name"])
        )
        self.type: str = ARG_TYPES.get(desc["type"])
        self.token = desc.get("token")
        self.backup_token: str = desc["name"]
        self.sanitized_token: str = (
            token_to_substitute.get(self.token, self.token)
            if self.token
            else snake_case(self.backup_token).upper()
        )
        self.is_optional: bool = desc.get("optional", False)
        self.is_variadic: bool = desc.get("multiple", False)
        self.must_have_label = False
        if self.token:
            self.token = self.token.replace('"', '\\"')

    def use_token_as_name(self):
        self.name = self.sanitized_token

    def parameter(self):
        return parameter_template.render(
            parameter_name=self.name,
            parameter_type=self.type,
            is_optional=self.is_optional,
            is_variadic=self.is_variadic,
            must_have_label=self.must_have_label,
        )

    def test_parameter(self):
        return test_parameter_template.render(
            parameter_name=self.name,
            parameter_value=self.test_value(),
        )

    def test_value(self):
        return TEST_VALUES.get(self.type)

    def is_option(self):
        return self.type == "token"


def parse_args(
    args: List[Dict], parent_name: str, make_options_arg=True, are_sub_args=False
):
    parsed_args: List[Argument] = []
    optional_args: List[Argument] = []
    used_arg_names: Set[str] = set()

    for arg in args:
        if arg["type"] == "oneof":
            from parsing_types.enum_argument import EnumArgument

            new_arg = EnumArgument(parent_name, arg, are_sub_args)
        elif arg["type"] == "block":
            from parsing_types.struct_argument import StructArgument

            new_arg = StructArgument(parent_name, arg, are_sub_args)
        else:
            new_arg = Argument(arg)

        if new_arg.name in used_arg_names:
            new_arg.use_token_as_name()
        else:
            used_arg_names.add(new_arg.name)

        if not new_arg.name in arguments_to_ignore:
            if new_arg.is_option() and make_options_arg:
                optional_args.append(new_arg)
            else:
                parsed_args.append(new_arg)

    if len(optional_args) > 0:
        from parsing_types.options_argument import OptionsArgument

        parsed_args.append(OptionsArgument(parent_name, optional_args, are_sub_args))

    if len(parsed_args) > 1:
        for index in range(len(parsed_args)):
            if index > 0 and parsed_args[index - 1].is_variadic:
                parsed_args[index].must_have_label = True

    return parsed_args
