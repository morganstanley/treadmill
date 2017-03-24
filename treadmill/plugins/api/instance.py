"""Instance plugin.
Adds proid and environment attributes based on request context.
"""


def add_attributes(rsrc_id, manifest):
    """Add additional attributes to the manifest."""
    proid = rsrc_id[0:rsrc_id.find('.')]
    environment = 'dev'
    updated = {
        'proid': proid,
        'environment': environment
    }
    updated.update(manifest)
    return updated


def remove_attributes(manifest):
    """Removes extra attributes from the manifest."""
    if 'proid' in manifest:
        del manifest['proid']
    if 'environment' in manifest:
        del manifest['environment']

    return manifest
