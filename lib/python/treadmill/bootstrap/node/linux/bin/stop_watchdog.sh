#!{{ _alias.execlineb }}

{{ _alias.foreground }} {
    {{ _alias.echo }} "Terminating watchdog daemon"
}
{{ _alias.backtick }} -n WATCHDOG_PID {
    {{ _alias.cat }} /var/run/watchdog.pid
}
{{ _alias.importas }} -u -i WATCHDOG_PID WATCHDOG_PID
{{ _alias.foreground }} {
    {{ _alias.kill }} -15 ${WATCHDOG_PID}
}
{{ _alias.foreground }} {
    {{ _alias.loopwhilex }}
        {{ _alias.backtick }} -n WATCHDOG_STATUS {
            {{ _alias.ps }} -o stat= ${WATCHDOG_PID}
        }
        {{ _alias.importas }} -u -i WATCHDOG_STATUS WATCHDOG_STATUS
        # check if watchdog still exists
        {{ _alias.backtick }} -n WATCHDOG_EXIST {
            {{ _alias.expr }} length ${WATCHDOG_STATUS}
        }
        {{ _alias.importas }} -u -i WATCHDOG_EXIST WATCHDOG_EXIST
        # check if watchdog becomes zombie
        {{ _alias.backtick }} -n WATCHDOG_ZOMBIE {
            {{ _alias.expr }} index ${WATCHDOG_STATUS} Z
        }
        {{ _alias.importas }} -u -i WATCHDOG_ZOMBIE WATCHDOG_ZOMBIE
        # keep looping until watchdog exits or becomes a zombie
        {{ _alias.expr }} ${WATCHDOG_EXIST} > 0 & ${WATCHDOG_ZOMBIE} = 0
}
{{ _alias.foreground }} {
    {{ _alias.echo }} "Watchdog daemon terminated"
}
