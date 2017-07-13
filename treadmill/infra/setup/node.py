from treadmill.infra import instances


class Node:
    def __init__(self):
        self.instances = None

    def setup(self, name, image_id, count, subnet_id, secgroup_ids):
        self.instances = instances.Instances.create(
            name=name,
            image_id=image_id,
            count=count,
            subnet_id=subnet_id,
            secgroup_ids=secgroup_ids
        )

        return self.instances

    def terminate(self):
        self.instances.terminate()
