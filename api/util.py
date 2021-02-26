class InvalidInstantiationError(Exception):
    def __init__(self, origin_class_name, missing_argument_name, missing_argument_type, instantiation_method_to_use):

        message = """Invalid instantiation for class '{class_name}':
                  missing instantiation argument '{arg}' of type '{arg_type}'.
                  Please use the '{method_name}' factory class method""" \
            .format(class_name=origin_class_name,
                    arg=missing_argument_name,
                    arg_type=missing_argument_type,
                    method_name=instantiation_method_to_use)

        # Call the base class constructor with the parameters it needs
        super(InvalidInstantiationError, self).__init__(message)

def member_exists(obj, member, of_type):
    member_value = getattr(obj, member, None)

    if member_value is None:
        return False

    if not isinstance(member_value, of_type):
        return False

    return True

def must_have(obj, member, of_type, use_method):
        if not member_exists(obj, member, of_type=of_type):
            raise InvalidInstantiationError(obj.__class__.__name__,
                                            member,
                                            of_type.__name__,
                                            use_method)