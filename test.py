import pkg_resources

with open('requirements.txt') as f:
    reqs = f.readlines()

ws = pkg_resources.WorkingSet()
e = pkg_resources.Environment()

for req in reqs:
    req = pkg_resources.Requirement(req)
    dist = ws.find(req)
