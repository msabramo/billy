# Filter decorator & misc backup functions

bill_filters = {
    "default" : [ "fix_bill_id" ]
}

legislator_filters = {
    "default" : []
}
committee_filters  = {
    "default" : []
}
vote_filters       = {
    "default" : []
}

# ----------------- Cut above this line -----------------

filters = {}

def register_filter( function ) :
    name = function.__name__

    if name in filters:
        raise KeyError( "Filter already exists" )
    filters[name] = function
    return function

import billy.importers.filters
