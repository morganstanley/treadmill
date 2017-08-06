from treadmill.plugins.scheduler import predicates


class MatchAppConstraints(predicates.PredicateConfig):
    def predicate(self, app, node):
        for level in app.affinity.limits:
            if not node.parent_counters.get(level):
                continue
            for counter in node.parent_counters[level]:
                if (counter[app.affinity.name] >=
                        app.affinity.limits[level]):
                    return False
        if node.check_app_constraints(app):
            return True
        return False


def match_app_constraints():
    return MatchAppConstraints()
