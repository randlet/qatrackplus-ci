.. _qa_perform:

Performing a Test List
======================

Selecting a test list
---------------------

To perform a test list, first login to QATrack+ and then select the
**Choose Unit** option from the **Perform QA** dropdown menu.

.. figure:: images/choose_unit_menu.png
   :alt: Choose Unit Menu Option

   Choose Unit Menu Option

On the following page, clicking on the main button for a unit will take
you to a page that lists all the test lists assigned to that unit.

.. figure:: images/select_unit_button.png
   :alt: Select unit button

   Select unit button

You can pre-filter the list by its assigned frequency by using the
dropdown menu attached to the select unit button.

.. figure:: images/select_unit_dropdown.png
   :alt: Select unit dropdown button

   Select unit dropdown button

On the next page, all the test lists with the chosen frequency will be
displayed along with relevant information about the last time that test
list was performed and when the test list is next due on this unit.

Click on the **Perform QA** button next to the list that you would like
to complete.

.. figure:: images/choose_test_list.png
   :alt: Choose a test list to perform

   Choose a test list to perform

Performing a test list
----------------------

An example test list is shown below. Details about all the features will
given below but briefly, you can see all the tests completed and ready
to be submitted. The shaded input boxes for the last two tests indicate
that they are `composite tests <../../admin/qa/tests.html>`__ i.e. they are test
values calculated based on the other 4 input values. Passing, tolerance
and failing tests are displayed with a green, yellow or red status,
respectively. Tests which have no reference or tolerance set for them
are shown in blue.

.. figure:: images/example_test_list.png
   :alt: Example test list

   Example test list


Viewing test procedures
~~~~~~~~~~~~~~~~~~~~~~~

Clicking on the test name will display instructions or information about
performing the test.

.. figure:: images/test_procedure.png
   :alt: Embedded test procedure

   Embedded test procedure


Adding comments
~~~~~~~~~~~~~~~

You may add either test specific comments by clicking on the speech
bubble beside the test or you can add a general comment for the whole
test list by entering the comment in the text box below the `Submit QA Results` button.

`Adding comments to a test list <add_comment.png>`__

.. figure:: images/add_comment.png
   :alt: Adding comments to test lists

   Adding comments to test lists


Skipping a test
~~~~~~~~~~~~~~~

Occasionally it may be required to skip a test when performing a test list. To
accomplish this, check off the **skip** checkbox next to the test and add a
comment (required unless the user has the `Can skip without comment
<../../admin/qa/auth.rst>`__ permission) explaining why you are skipping the test.

.. figure:: images/skip_test.png
   :alt: Skipping a single test

   Skipping a single test


.. _qa_perform_subset:

Performing a subset of a test list
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Some test lists may have tests from more than one `category type
<../admin/qa/categories>`__. To selectively perform the tests from one or
more categories, use the select box from the left hand drawer menu to choose
the test categories you want to perform. Tests from categories that are not
selected, will be hidden and marked as skipped with a comment explaining why.

.. figure:: images/perform_subset.png
   :alt: Performing a subset (Dosimetry & AQA) of tests within a test list

   Performing a subset (Dosimetry & AQA) of tests within a test list


Attaching Files to your session
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _attaching_files:

When performing QA, you may attach arbitrary documents to the test list before
submitting (e.g.  a PDF report from some external software).

In order to do this, simply click the `Browse` button and select the files you
want to attach.

.. figure:: images/attach_button.png
   :alt: Attaching files to a test list instance

   Attaching files to a test list instance


These files will be saved and available for review later.


Keyboard Shortcuts
~~~~~~~~~~~~~~~~~~

There are currently a limited number of keyboard shortcuts available when
performing a test list:

* Use the up/down arrow keys to navigate between test input fields
* Hit Enter or Tab to cycle through the test input fields

More keyboard shortcuts will be made available in the future.


Saving a test list to complete it later
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If for some reason you need to finish a test list at a later time, you
can click the **Mark this list as still in progress** checkbox next to
the **Submit QA Results** button. When this box is checked, the test
list will not be considered complete and will not be marked for review.

.. figure:: images/save_for_later.png
   :alt: Save a test list to complete later

   Save a test list to complete later

When you are ready to complete the test list, you can find it by
selecting the **In Progress** menu option

.. figure:: images/in_progress_menu.png
   :alt: In progress menu

   In progress menu

and then clicking **Continue** on your saved result.

.. figure:: images/continue_in_progress.png
   :alt: Continue an in progress test list

   Continue an in progress test list

When performing a test list, the left hand drawer menu will also show any In
Progress QA sessions for the current test list.

.. figure:: images/in_progress_sidebar.png
   :alt: Continue an in progress test list from the sidebar

   Continue an in progress test list from the sidebar
