from ...predicates import PredicateConfig


class MatchAppConstraints(PredicateConfig):
    def predicate(self, app, node):
        if node.check_app_constraints(app):
            return True
        return False


def match_app_constraints():
    return MatchAppConstraints()
