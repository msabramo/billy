# Filter decorator & misc backup functions

filters = {}

def register_filter( function ) :
    name = function.__name__

    if name in filters:
        raise KeyError( "Filter already exists" )
    filters[name] = function
    return function

import billy.importers.filters
