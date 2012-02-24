# Filter decorator & misc backup functions

bill_filters = {
    "bill_id" : [ "fix_bill_id" ]
}
filters = {}

def filter_bill_dict( obj ):
    for attr in obj:
        if attr in bill_filters:
            filts = bill_filters[attr]
            for f in filts:
                obj[attr] = filters[f](obj[attr])
    return obj

# ----------------- Cut above this line -----------------

def register_filter( function ) :
    name = function.__name__

    if name in filters:
        raise KeyError( "Filter already exists" )
    filters[name] = function
    return function

import billy.importers.filters
