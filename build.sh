#!/bin/bash

reset_repository () {
    rm -rf CGAL-5.6*

    cd fastjet-core
    git reset --hard fastjet-3.4.2
    git clean -f
    cd ..
}

reset_fastjet_contrib () {
    cd fastjet-contrib
    # git reset --hard v1.014
    git reset --hard aa1972cd2b3e8aa2c76764f14122e8f728c23712
    git clean -f
    cd ..
}

reset_repository
reset_fastjet_contrib

rm -rf build
python -m pip install --upgrade --verbose .

reset_repository
