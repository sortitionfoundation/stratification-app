# Strat App

The strat app is for selecting a set of people from a population, so that the set of people have a mix of demographics that match the given targets.

For example, you might have 100 people in your population and you want to select:

* 20 people
* about half male, half female, 0 or 1 other
* half urban and half rural
* 4 18-29 year olds, 5 30-44, 7 45-64 and 4 65+. (+/- 1 for each category)

The app will produce a list of people matching the demographic targets given.  (Or it will tell you that the targets cannot be met given this population.)

## Input and Output

There are 2 tables that go in:

- one for the population - this has one row for each person, with their details, including demographics in each column.
- the other defining the targets - this has one row for each demographic value, with the category, the value and the minimum and maximum number of people to select with that value.

One table comes out:

- the selected people - the same columns as for the population, but just the rows of those selected.
- the remaining people - the same columns as for the population, but just the rows of those who were not selected.

The software accepts files as CSV files on local disk, or it can talk to Google Spreadsheets.

### CSV Files

Here are some bits of example files.  Note that the files should have the first row be the titles of each column.

If we had a people CSV with the following first couple of rows:

``` CSV
nationbuilder_id,first_name,last_name,email,mobile_number,primary_address1,primary_address2,primary_city,primary_zip,gender,age_bracket,geo_bucket,edu_level
p0,Hamish,McDonald,hamishm@scotland.com,07123456789,11 Scots Drive,,Glasgow,G1 1AA,Male,30-44,South Scotland,Level 4 and above
p1,Margaret,Campbell,marge@highlands.org,07234567890,22 Heather Lane,,Inverness,IV1 1AA,Female,16-29,Lothian,Level 1
...
```

Then the categories could be:

``` CSV
category,name,min,max,min_flex,max_flex
gender,Female,11,12,10,13
gender,Male,10,11,9,13
gender,Non-binary or other,0,1,0,1
age_bracket,0-15,0,0,0,0
age_bracket,16-29,5,7,4,8
age_bracket,30-44,5,7,4,8
age_bracket,45-59,5,6,4,7
age_bracket,60+,5,6,4,7
edu_level,No qualifications,5,7,4,8
edu_level,Level 1,5,7,4,8
edu_level,Level 2 or 3,5,6,4,7
edu_level,Level 4 and above,5,6,4,7
geo_bucket,Central Scotland,3,5,2,6
geo_bucket,Glasgow,3,5,2,6
geo_bucket,Highlands and Islands,2,5,1,6
geo_bucket,Lothian,3,5,2,6
geo_bucket,Mid Scotland and Fife,3,5,2,6
geo_bucket,North East Scotland,2,5,1,6
geo_bucket,South Scotland,3,5,2,6
geo_bucket,West Scotland,3,5,2,6
```

Note the columns here are:

- `category`
- `name`
- `min`
- `max`
- `min_flex`
- `max_flex`

`min_flex` and `max_flex` are used by some algorithms to suggest alternative targets that would be achievable, but only if the actual targets (`min` and `max`) are not achievable.  In the above example all the `min_flex` values are one less than the `min` (or 0 if `min` is 0) and all the `max_flex` values are one more than the `max`.

### Google Spreadsheets

In this case, the input and output tables are all tabs (aka worksheets) within a single Google Spreadsheet.

The app will let you search for the Spreadsheet by name - it should have a unique name among the spreadsheets your Google user has access to.

You can select what the names of the input tabs are - the defaults are "Categories" and "Respondents".

It will create new tabs, with the default names (if they don't already exist) of "X" and "Y".  **TODO:** fix this line.

## Config Files

There are two main config files.  One is general config for the app.  The second is required to talk to Google Spreadsheets.

### sf_stratification_settings.toml

This should be in your home directory.  Sample contents are:

``` toml
# this is the name of the (unique) field for each person
id_column = "nationbuilder_id"

# if check_same_address is true, then no 2 people from the same address will be selected
# the comparison checks if the TWO fields listed here are the same for any person
check_same_address = true
check_same_address_columns = [
    "primary_address1",
    "zip_royal_mail"
]

max_attempts = 100
columns_to_keep = [
    "first_name",
    "last_name",
    "mobile_number",
    "email",
    "primary_address1",
    "primary_address2",
    "primary_city",
    "zip_royal_mail",
    "tag_list",
    "age",
    "gender"
]

# selection_algorithm can either be "legacy", "maximin", "leximin", or "nash"
selection_algorithm = "leximin"

# random number seed - if this is NOT zero then it is used to set the random number generator seed
random_number_seed = 0
```

### secret_do_not_commit.json

This contains secrets used to talk to Google Spreadsheets.
