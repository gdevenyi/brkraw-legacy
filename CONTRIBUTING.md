# Contributing to BrkRaw-legacy

Thank you for your interest in contributing to BrkRaw-legacy! Whether you're tackling a bug, adding a new feature, or improving our documentation, every contribution is appreciated. This guide will help you get started with your contributions in the most effective way.

BrkRaw-legacy is an independent hard fork of the [BrkRaw](https://github.com/BrkRaw/brkraw) 0.3.x/0.4 line. Contributions here are not submitted upstream, and upstream changes are not merged in. If your contribution targets the current 0.5+ BrkRaw architecture, please direct it to the upstream project instead.

## Ways to Contribute

### Reporting Issues

If you encounter a bug, have a suggestion, or want to make a feature request, please use the [Issues](https://github.com/gdevenyi/brkraw-legacy/issues) section of this repository. Include as much detail as possible and label your issue appropriately.

### Pull Requests

We welcome pull requests with open arms! Here’s how you can make one:

- **Code Changes**: If you are updating the BrkRaw-legacy codebase, perhaps due to a ParaVision compatibility issue or to suggest a new standard, please make sure your changes are well-documented. 
- **New Features**: If you're introducing a new feature, ensure that you include appropriate test scripts in the `tests` directory, following our standard testing workflow. Check our documentation for more details.

Before creating a pull request, ensure that your code complies with the existing code style (`ruff check .`) and that you have tested your changes locally.

### Related Upstream Repositories

These repositories belong to the upstream BrkRaw project. This fork still consumes their data and plugins, but contributions to them go to upstream, not here.

- **[plugin](https://github.com/brkraw/brkraw-plugin.git)**: New functionalities at the app level.
- **[dataset](https://github.com/brkraw/brkraw-dataset.git)**: Datasets used to test data conversion consistency and reliability.
- **[tutorial](https://github.com/brkraw/brkraw-tutorial.git)**: Tutorials, tutorial revisions, and user documentation.

## Before You Start

Please review the documentation and Q&A to see if your question has already been answered or if the feature has already been discussed. If you’re unsure about adding a feature or making a change, open an issue to discuss it first.

## Contribution Guidelines

- Ensure your contributions are clear and easy to understand.
- Include any necessary tests and documentation updates.
- Adhere to the coding standards and best practices as outlined in our project documentation.

We look forward to your contributions and are excited to see what you come up with!
