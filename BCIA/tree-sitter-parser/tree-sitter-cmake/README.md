# A Better Tree-sitter Parser for CMake

This repository provides an accurate `CMake` parser generator based on [tree-sitter](https://tree-sitter.github.io/).
Up until August 10th, 2024, the parser has been tested on over 10,000 commits that modify `CMake` build specifications with no errors.
It has been improved to successfully parse all supported syntax in `CMake` based on its [documentation](https://cmake.org/cmake/help/v3.0/manual/cmake-language.7.html\#syntax).


## Setup

To generate the parser, follow the instructions for [creating parsers using tree-sitter](https://tree-sitter.github.io/tree-sitter/creating-parsers).
Specifically, you can take the following steps:


1. Make sure you have the [dependencies](https://tree-sitter.github.io/tree-sitter/creating-parsers#dependencies) installed.
    > Note: This parser is developed and tested with `Node.js v12.22.9` and `npm 8.5.1`.

2. Install the [tree-sitter-cli](https://tree-sitter.github.io/tree-sitter/creating-parsers#installation).

3. When going through the [project setup steps](https://tree-sitter.github.io/tree-sitter/creating-parsers#project-setup), instead of creating a new directory, navigate to the root directory of a local clone of this repository. Then move forward with the steps from [here](https://tree-sitter.github.io/tree-sitter/creating-parsers#project-setup:~:text=You%20can%20use%20the%20npm%20command%20line%20tool%20to%20create%20a%20package.json%20file%20that%20describes%20your%20project%2C%20and%20allows%20your%20parser%20to%20be%20used%20from%20Node.js.).