LABELS = {'place': 'Place', 'nisar': 'Open water outside the usual water', 'rainfall': 'Pass rainfall', 'imerg': 'IMERG rain',
          'motion': 'Line-of-sight motion', 'priority': 'Priority zone', 'exposure': 'Exposure'}
UNAVAILABLE = 'not available because'
FLOOD = 'open water outside the usual water detected on {count} of {valid} valid passes'
IMERG = 'on the latest pass at {when} Manila time, {rain24} mm fell in the preceding {hours24} hours and {rain48} mm in {hours48} hours; {since} hours since the last half-hour with an area-mean rain rate at or above {threshold} mm/hour'
LIMIT = 'Flooded streets can look bright to radar and may be missed by the open-water rule; passes around {time} Manila time can miss floods that drain before morning'
MOTION_UNAVAILABLE = 'not available yet'
PRIORITY_YES = 'this point is in the priority zone'
PRIORITY_NO = 'this point is outside the priority zone'
EXPOSURE = 'barangay exposure: {area} km², {population} people, {buildings} mapped buildings'
RAINFALL = '{rain} mm in the seven days before the pass on {date}'
MOTION = 'line-of-sight displacement {displacement} mm on {date}; positive values are away from the satellite'
