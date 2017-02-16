# Install packages needed
`for package in $(cat earEEG/apt-packages.txt); do apt-get install $package; done;`

# Install virtualenvwrapper
`pip install virtualenvwrapper`  
`source /usr/local/bin/virtualenvwrapper.sh`

# Clone the repo
`git clone https://github.com/jherwig1/EarEEG`

# Create python virtual environment
`mkvirtualenv -a EarEEG -r requirements.txt ENV-NAME`

# Install npm modules
`npm install`

You need to have these modules in your environment path. The simplest
way to do this is to edit your virtualenv settings.

In ~/.virtualenvs/postactivate, add:
```
export DEACTIVATE_PATH=$PATH  
export PATH=$PWD/node_modules/.bin:$PATH
```

In ~/.virtualenvs/postdeactivate, add:
```
export PATH=$DEACTIVATE_PATH  
unset DEACTIVATE_PATH
```

# Install bower components
`bower install`

# Run grunt to produce minified/uglified bundle of JS dependencies
`grunt requirejs`

# Run the application (local only, don't do this in production)
`python manage.py runserver`
