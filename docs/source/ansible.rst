Ansible
=======
Playbooks
^^^^^^^^^^
Playbooks describe a set of steps to be performed on remote systems.

**For ex:** We have top level playbooks for creating/destroying the cell *(cell.yml/destroy-cell.yml)* , creating masters/nodes *(master.yml/node.yml)* etc.

A playbook contains different plays and a play contains:

* **hosts:** Defines the inventory of hosts for running the steps.
* **pre_tasks:** Tasks to be performed before performing the main task.
* **tasks:** Actual tasks to performed.
* **roles:** Roles to be executed.

Roles 
^^^^^^
Roles are the way of organizing playbooks.

**For ex:** *deploy/master.yml* playbook calls *instance* and *dynamic-inventory* roles.

* **templates:** jinja2 templates in the templates directory of a role *(deploy/roles/master/templates/zoo.cfg)*

* **meta/main.yml:** Defines the dependent roles to be executed prior to the main role.

* **tasks/main.yml:** Actual tasks to be executed on the hosts provided.

Modules
^^^^^^^^
Modules are what gets executed in each playbook task.

Few examples of ansible modules that we are using are: *ec2, ec2_group, uri, file, template etc.*

Inventory
^^^^^^^^^
An inventory file contains a list of hosts.

* *deploy/controller.inventory* file contains the mapping of *controller* to localhost. Hence we have used *controller* as *hosts* to run a play on localhost.
* For provisioning masters/nodes, we are creating a dynamic inventory of hosts by filtering them out. For ex - *ec2instances.*

Config file
^^^^^^^^^^^^
Configuration file for AWS *(deploy/config/aws.yml)*
