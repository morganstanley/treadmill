from treadmill.plugins.scheduler import predicates


class MatchAppLifetime(predicates.PredicateConfig):
    def predicate(self, app, node):
        if node.check_app_lifetime(app):
            return True
        return False


def match_app_lifetime():
    return MatchAppLifetime()
