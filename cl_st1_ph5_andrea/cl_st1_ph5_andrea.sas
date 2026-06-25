/* ANOVA - CL_St1_Ph5_andrea_ANOVA */

/*
   Phase 5 objective:
   Conduct ANOVAs to detect diachronic variation in:
   1. verbal discourses;
   2. visual discourses;
   3. cross-modal discourses.

   Input:
   tv_commercials_cca_scores.tsv

   This file is expected to contain:
   - file_id
   - group_filename
   - decade
   - verbal factor scores: ver1-ver8
   - visual factor scores: vis1-vis8
   - canonical variate scores: V1-V8 and W1-W8

   Only canonical dimensions 1-7 are used for cross-modal ANOVAs,
   because only the first seven canonical dimensions are statistically significant.
*/

/* ------------------------------------------------------------------ */
/* 1. PROJECT SETTINGS                                                */
/* ------------------------------------------------------------------ */

/* Match this to the actual folder in SAS OnDemand */
%LET project = cl_st1_ph5_andrea_ANOVA;
%LET myfolder = &project;

/* Replace with your SAS user ID */
%LET sasusername = u63529080;
%LET whereisit = /home/&sasusername;

/* Input file exported from Phase 4 CCA */
%LET inputfile = tv_commercials_cca_scores.tsv;

/* Main HTML output */
%LET resultsfile = tv_commercials_phase5_anova-results.html;

/* Output ZIP file */
%LET addcntzip = /home/&sasusername/zip/output_&project..zip;

/* ------------------------------------------------------------------ */
/* 2. IMPORT PHASE 4 CCA SCORE DATA                                    */
/* ------------------------------------------------------------------ */

PROC IMPORT DATAFILE="&whereisit/&myfolder/&inputfile"
            OUT=tv_commercials_cca_scores
            DBMS=TAB
            REPLACE;
   GETNAMES=YES;
   GUESSINGROWS=MAX;
RUN;

/* Inspect imported data */
PROC CONTENTS DATA=work.tv_commercials_cca_scores;
RUN;

/* Check decade distribution */
PROC FREQ DATA=work.tv_commercials_cca_scores;
    TABLES decade / MISSING;
RUN;

/* Descriptive statistics for verbal, visual, and canonical scores */
PROC MEANS DATA=work.tv_commercials_cca_scores N NMISS MEAN STD MIN MAX;
    CLASS decade;
    VAR ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8
        vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8
        V1 V2 V3 V4 V5 V6 V7
        W1 W2 W3 W4 W5 W6 W7;
RUN;

/* Overall descriptive statistics without decade grouping */
PROC MEANS DATA=work.tv_commercials_cca_scores N NMISS MEAN STD MIN MAX;
    VAR ver1 ver2 ver3 ver4 ver5 ver6 ver7 ver8
        vis1 vis2 vis3 vis4 vis5 vis6 vis7 vis8
        V1 V2 V3 V4 V5 V6 V7
        W1 W2 W3 W4 W5 W6 W7;
RUN;

/* ------------------------------------------------------------------ */
/* 3. CREATE PHASE 5 SCORE DATA WITH CROSS-MODAL COMPOSITES            */
/* ------------------------------------------------------------------ */

DATA tv_commercials_phase5_scores;
    SET work.tv_commercials_cca_scores;

    cross1 = MEAN(V1, W1);
    cross2 = MEAN(V2, W2);
    cross3 = MEAN(V3, W3);
    cross4 = MEAN(V4, W4);
    cross5 = MEAN(V5, W5);
    cross6 = MEAN(V6, W6);
    cross7 = MEAN(V7, W7);
RUN;

/* ------------------------------------------------------------------ */
/* 4. OPEN MAIN HTML RESULTS                                           */
/* ------------------------------------------------------------------ */

ODS HTML FILE="&whereisit/&myfolder/&resultsfile"
         STYLE=HTMLBlue;

TITLE "Phase 5 ANOVAs for &project";
ODS NOPROCTITLE;
ODS GRAPHICS / IMAGEMAP=ON;

/* ------------------------------------------------------------------ */
/* 5. SET UP EMPTY OUTPUT TABLES                                       */
/* ------------------------------------------------------------------ */

DATA anova_verbal_model;
    LENGTH analysis $20 measure $20 Source $80;
    STOP;
RUN;

DATA anova_verbal_overall;
    LENGTH analysis $20 measure $20 Source $80;
    STOP;
RUN;

DATA means_verbal;
    LENGTH analysis $20 measure $20 decade 8;
    STOP;
RUN;

DATA lsmeans_verbal;
    LENGTH analysis $20 measure $20;
    STOP;
RUN;

DATA diffs_verbal;
    LENGTH analysis $20 measure $20;
    STOP;
RUN;

DATA anova_visual_model;
    LENGTH analysis $20 measure $20 Source $80;
    STOP;
RUN;

DATA anova_visual_overall;
    LENGTH analysis $20 measure $20 Source $80;
    STOP;
RUN;

DATA means_visual;
    LENGTH analysis $20 measure $20 decade 8;
    STOP;
RUN;

DATA lsmeans_visual;
    LENGTH analysis $20 measure $20;
    STOP;
RUN;

DATA diffs_visual;
    LENGTH analysis $20 measure $20;
    STOP;
RUN;

DATA anova_crossmodal_model;
    LENGTH analysis $20 measure $20 Source $80;
    STOP;
RUN;

DATA anova_crossmodal_overall;
    LENGTH analysis $20 measure $20 Source $80;
    STOP;
RUN;

DATA means_crossmodal;
    LENGTH analysis $20 measure $20 decade 8;
    STOP;
RUN;

DATA lsmeans_crossmodal;
    LENGTH analysis $20 measure $20;
    STOP;
RUN;

DATA diffs_crossmodal;
    LENGTH analysis $20 measure $20;
    STOP;
RUN;

DATA anova_crosscomp_model;
    LENGTH analysis $20 measure $20 Source $80;
    STOP;
RUN;

DATA anova_crosscomp_overall;
    LENGTH analysis $20 measure $20 Source $80;
    STOP;
RUN;

DATA means_crosscomp;
    LENGTH analysis $20 measure $20 decade 8;
    STOP;
RUN;

DATA lsmeans_crosscomp;
    LENGTH analysis $20 measure $20;
    STOP;
RUN;

DATA diffs_crosscomp;
    LENGTH analysis $20 measure $20;
    STOP;
RUN;

/* ------------------------------------------------------------------ */
/* 6. MACRO TO RUN ONE ANOVA AND APPEND OUTPUT TABLES                  */
/* ------------------------------------------------------------------ */

%MACRO run_one_anova(
    data_in=,
    depvar=,
    analysis=,
    out_model=,
    out_overall=,
    out_means=,
    out_lsmeans=,
    out_diffs=
);

    TITLE2 "&analysis ANOVA: &depvar by decade";

    ODS OUTPUT
        ModelANOVA = _m
        OverallANOVA = _o
        Means = _means
        LSMeans = _lsm
        Diffs = _diffs
    ;

    PROC GLM DATA=&data_in;
        CLASS decade;
        MODEL &depvar = decade;
        MEANS decade / HOVTEST=LEVENE;
        LSMEANS decade / PDIFF ADJUST=TUKEY;
    RUN;
    QUIT;

    ODS OUTPUT CLOSE;

    %IF %SYSFUNC(EXIST(work._m)) %THEN %DO;
        DATA _m;
            LENGTH analysis $20 measure $20;
            SET _m;
            analysis = "&analysis";
            measure = "&depvar";
        RUN;

        PROC APPEND BASE=&out_model DATA=_m FORCE;
        RUN;
    %END;

    %IF %SYSFUNC(EXIST(work._o)) %THEN %DO;
        DATA _o;
            LENGTH analysis $20 measure $20;
            SET _o;
            analysis = "&analysis";
            measure = "&depvar";
        RUN;

        PROC APPEND BASE=&out_overall DATA=_o FORCE;
        RUN;
    %END;

    %IF %SYSFUNC(EXIST(work._means)) %THEN %DO;
        DATA _means;
            LENGTH analysis $20 measure $20;
            SET _means;
            analysis = "&analysis";
            measure = "&depvar";
        RUN;

        PROC APPEND BASE=&out_means DATA=_means FORCE;
        RUN;
    %END;

    %IF %SYSFUNC(EXIST(work._lsm)) %THEN %DO;
        DATA _lsm;
            LENGTH analysis $20 measure $20;
            SET _lsm;
            analysis = "&analysis";
            measure = "&depvar";
        RUN;

        PROC APPEND BASE=&out_lsmeans DATA=_lsm FORCE;
        RUN;
    %END;

    %IF %SYSFUNC(EXIST(work._diffs)) %THEN %DO;
        DATA _diffs;
            LENGTH analysis $20 measure $20;
            SET _diffs;
            analysis = "&analysis";
            measure = "&depvar";
        RUN;

        PROC APPEND BASE=&out_diffs DATA=_diffs FORCE;
        RUN;
    %END;

    PROC DATASETS LIBRARY=work NOLIST;
        DELETE _m _o _means _lsm _diffs;
    QUIT;

%MEND run_one_anova;

/* ------------------------------------------------------------------ */
/* 7. VERBAL DISCOURSE ANOVAS                                          */
/* ------------------------------------------------------------------ */

TITLE2 "Verbal discourse ANOVAs: ver1-ver8 by decade";

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=ver1,
    analysis=verbal,
    out_model=anova_verbal_model,
    out_overall=anova_verbal_overall,
    out_means=means_verbal,
    out_lsmeans=lsmeans_verbal,
    out_diffs=diffs_verbal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=ver2,
    analysis=verbal,
    out_model=anova_verbal_model,
    out_overall=anova_verbal_overall,
    out_means=means_verbal,
    out_lsmeans=lsmeans_verbal,
    out_diffs=diffs_verbal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=ver3,
    analysis=verbal,
    out_model=anova_verbal_model,
    out_overall=anova_verbal_overall,
    out_means=means_verbal,
    out_lsmeans=lsmeans_verbal,
    out_diffs=diffs_verbal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=ver4,
    analysis=verbal,
    out_model=anova_verbal_model,
    out_overall=anova_verbal_overall,
    out_means=means_verbal,
    out_lsmeans=lsmeans_verbal,
    out_diffs=diffs_verbal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=ver5,
    analysis=verbal,
    out_model=anova_verbal_model,
    out_overall=anova_verbal_overall,
    out_means=means_verbal,
    out_lsmeans=lsmeans_verbal,
    out_diffs=diffs_verbal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=ver6,
    analysis=verbal,
    out_model=anova_verbal_model,
    out_overall=anova_verbal_overall,
    out_means=means_verbal,
    out_lsmeans=lsmeans_verbal,
    out_diffs=diffs_verbal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=ver7,
    analysis=verbal,
    out_model=anova_verbal_model,
    out_overall=anova_verbal_overall,
    out_means=means_verbal,
    out_lsmeans=lsmeans_verbal,
    out_diffs=diffs_verbal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=ver8,
    analysis=verbal,
    out_model=anova_verbal_model,
    out_overall=anova_verbal_overall,
    out_means=means_verbal,
    out_lsmeans=lsmeans_verbal,
    out_diffs=diffs_verbal
);

/* ------------------------------------------------------------------ */
/* 8. VISUAL DISCOURSE ANOVAS                                          */
/* ------------------------------------------------------------------ */

TITLE2 "Visual discourse ANOVAs: vis1-vis8 by decade";

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=vis1,
    analysis=visual,
    out_model=anova_visual_model,
    out_overall=anova_visual_overall,
    out_means=means_visual,
    out_lsmeans=lsmeans_visual,
    out_diffs=diffs_visual
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=vis2,
    analysis=visual,
    out_model=anova_visual_model,
    out_overall=anova_visual_overall,
    out_means=means_visual,
    out_lsmeans=lsmeans_visual,
    out_diffs=diffs_visual
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=vis3,
    analysis=visual,
    out_model=anova_visual_model,
    out_overall=anova_visual_overall,
    out_means=means_visual,
    out_lsmeans=lsmeans_visual,
    out_diffs=diffs_visual
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=vis4,
    analysis=visual,
    out_model=anova_visual_model,
    out_overall=anova_visual_overall,
    out_means=means_visual,
    out_lsmeans=lsmeans_visual,
    out_diffs=diffs_visual
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=vis5,
    analysis=visual,
    out_model=anova_visual_model,
    out_overall=anova_visual_overall,
    out_means=means_visual,
    out_lsmeans=lsmeans_visual,
    out_diffs=diffs_visual
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=vis6,
    analysis=visual,
    out_model=anova_visual_model,
    out_overall=anova_visual_overall,
    out_means=means_visual,
    out_lsmeans=lsmeans_visual,
    out_diffs=diffs_visual
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=vis7,
    analysis=visual,
    out_model=anova_visual_model,
    out_overall=anova_visual_overall,
    out_means=means_visual,
    out_lsmeans=lsmeans_visual,
    out_diffs=diffs_visual
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=vis8,
    analysis=visual,
    out_model=anova_visual_model,
    out_overall=anova_visual_overall,
    out_means=means_visual,
    out_lsmeans=lsmeans_visual,
    out_diffs=diffs_visual
);

/* ------------------------------------------------------------------ */
/* 9. CROSS-MODAL CANONICAL VARIATE ANOVAS                             */
/* ------------------------------------------------------------------ */

/*
   Cross-modal discourse scores are represented by canonical variate
   scores from PROC CANCORR.

   V1-V7 = verbal-side canonical variate scores.
   W1-W7 = visual-side canonical variate scores.

   Only dimensions 1-7 are included because they are statistically significant.
*/

TITLE2 "Cross-modal discourse ANOVAs: canonical variate scores V1-W7 by decade";

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=V1,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=W1,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=V2,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=W2,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=V3,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=W3,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=V4,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=W4,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=V5,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=W5,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=V6,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=W6,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=V7,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=W7,
    analysis=crossmodal,
    out_model=anova_crossmodal_model,
    out_overall=anova_crossmodal_overall,
    out_means=means_crossmodal,
    out_lsmeans=lsmeans_crossmodal,
    out_diffs=diffs_crossmodal
);

/* ------------------------------------------------------------------ */
/* 10. DERIVED CROSS-MODAL COMPOSITE ANOVAS                            */
/* ------------------------------------------------------------------ */

/*
   This section analyses one composite score per canonical dimension.

   Each composite is the mean of the verbal-side and visual-side
   canonical variate scores for the same canonical dimension.
*/

TITLE2 "Derived cross-modal composite ANOVAs: cross1-cross7 by decade";

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=cross1,
    analysis=crosscomp,
    out_model=anova_crosscomp_model,
    out_overall=anova_crosscomp_overall,
    out_means=means_crosscomp,
    out_lsmeans=lsmeans_crosscomp,
    out_diffs=diffs_crosscomp
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=cross2,
    analysis=crosscomp,
    out_model=anova_crosscomp_model,
    out_overall=anova_crosscomp_overall,
    out_means=means_crosscomp,
    out_lsmeans=lsmeans_crosscomp,
    out_diffs=diffs_crosscomp
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=cross3,
    analysis=crosscomp,
    out_model=anova_crosscomp_model,
    out_overall=anova_crosscomp_overall,
    out_means=means_crosscomp,
    out_lsmeans=lsmeans_crosscomp,
    out_diffs=diffs_crosscomp
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=cross4,
    analysis=crosscomp,
    out_model=anova_crosscomp_model,
    out_overall=anova_crosscomp_overall,
    out_means=means_crosscomp,
    out_lsmeans=lsmeans_crosscomp,
    out_diffs=diffs_crosscomp
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=cross5,
    analysis=crosscomp,
    out_model=anova_crosscomp_model,
    out_overall=anova_crosscomp_overall,
    out_means=means_crosscomp,
    out_lsmeans=lsmeans_crosscomp,
    out_diffs=diffs_crosscomp
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=cross6,
    analysis=crosscomp,
    out_model=anova_crosscomp_model,
    out_overall=anova_crosscomp_overall,
    out_means=means_crosscomp,
    out_lsmeans=lsmeans_crosscomp,
    out_diffs=diffs_crosscomp
);

%run_one_anova(
    data_in=work.tv_commercials_phase5_scores,
    depvar=cross7,
    analysis=crosscomp,
    out_model=anova_crosscomp_model,
    out_overall=anova_crosscomp_overall,
    out_means=means_crosscomp,
    out_lsmeans=lsmeans_crosscomp,
    out_diffs=diffs_crosscomp
);

/* ------------------------------------------------------------------ */
/* 11. EXPORT ANALYSIS DATA AND ANOVA RESULT TABLES                    */
/* ------------------------------------------------------------------ */

TITLE2 "Exported Phase 5 data and ANOVA tables";

PROC EXPORT DATA=work.tv_commercials_phase5_scores
            OUTFILE="&whereisit/&myfolder/tv_commercials_phase5_scores.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* Model ANOVA tables */

PROC EXPORT DATA=work.anova_verbal_model
            OUTFILE="&whereisit/&myfolder/anova_verbal_model.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_visual_model
            OUTFILE="&whereisit/&myfolder/anova_visual_model.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_crossmodal_model
            OUTFILE="&whereisit/&myfolder/anova_crossmodal_model.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_crosscomp_model
            OUTFILE="&whereisit/&myfolder/anova_crosscomp_model.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* Overall ANOVA tables */

PROC EXPORT DATA=work.anova_verbal_overall
            OUTFILE="&whereisit/&myfolder/anova_verbal_overall.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_visual_overall
            OUTFILE="&whereisit/&myfolder/anova_visual_overall.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_crossmodal_overall
            OUTFILE="&whereisit/&myfolder/anova_crossmodal_overall.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.anova_crosscomp_overall
            OUTFILE="&whereisit/&myfolder/anova_crosscomp_overall.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* Decade means tables */

PROC EXPORT DATA=work.means_verbal
            OUTFILE="&whereisit/&myfolder/means_verbal.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.means_visual
            OUTFILE="&whereisit/&myfolder/means_visual.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.means_crossmodal
            OUTFILE="&whereisit/&myfolder/means_crossmodal.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.means_crosscomp
            OUTFILE="&whereisit/&myfolder/means_crosscomp.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* LSMeans tables */

PROC EXPORT DATA=work.lsmeans_verbal
            OUTFILE="&whereisit/&myfolder/lsmeans_verbal.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.lsmeans_visual
            OUTFILE="&whereisit/&myfolder/lsmeans_visual.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.lsmeans_crossmodal
            OUTFILE="&whereisit/&myfolder/lsmeans_crossmodal.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.lsmeans_crosscomp
            OUTFILE="&whereisit/&myfolder/lsmeans_crosscomp.tsv"
            DBMS=TAB
            REPLACE;
RUN;

/* Tukey pairwise-comparison tables */

PROC EXPORT DATA=work.diffs_verbal
            OUTFILE="&whereisit/&myfolder/diffs_verbal.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.diffs_visual
            OUTFILE="&whereisit/&myfolder/diffs_visual.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.diffs_crossmodal
            OUTFILE="&whereisit/&myfolder/diffs_crossmodal.tsv"
            DBMS=TAB
            REPLACE;
RUN;

PROC EXPORT DATA=work.diffs_crosscomp
            OUTFILE="&whereisit/&myfolder/diffs_crosscomp.tsv"
            DBMS=TAB
            REPLACE;
RUN;

ODS HTML CLOSE;

/* ------------------------------------------------------------------ */
/* 12. ZIP OUTPUT FILES                                                */
/* ------------------------------------------------------------------ */

FILENAME temp "&addcntzip";

DATA _NULL_;
    rc = FDELETE('temp');
RUN;

DATA filelist;
RUN;

DATA filelist;
    LENGTH root dname $ 2048 filename $ 256 dir level 8;
    INPUT root;
    RETAIN filename dname ' ' level 0 dir 1;
CARDS4;
/home/u63529080/cl_st1_ph5_andrea_ANOVA
;;;;
RUN;

DATA filelist;
    MODIFY filelist;

    rc1 = FILENAME('tmp', CATX('/', root, dname, filename));
    rc2 = DOPEN('tmp');
    dir = 1 & rc2;

    IF dir THEN DO;
        dname = CATX('/', dname, filename);
        filename = ' ';
    END;

    REPLACE;

    IF dir;

    level = level + 1;

    DO i = 1 TO DNUM(rc2);
        filename = DREAD(rc2, i);
        OUTPUT;
    END;

    rc3 = DCLOSE(rc2);
RUN;

PROC SORT DATA=filelist;
    BY root dname filename;
RUN;

PROC PRINT DATA=filelist;
RUN;

DATA _NULL_;
    SET filelist;

    IF dir = 0;

    rc1 = FILENAME("in", CATX('/', root, dname, filename), "disk", "lrecl=1 recfm=n");
    rc1txt = SYSMSG();

    rc2 = FILENAME(
        "out",
        "&addcntzip.",
        "ZIP",
        "lrecl=1 recfm=n member='" !! CATX('/', dname, filename) !! "'"
    );
    rc2txt = SYSMSG();

    DO _N_ = 1 TO 6;
        rc3 = FCOPY("in", "out");
        rc3txt = SYSMSG();

        IF FEXIST("out") THEN LEAVE;
        ELSE sleeprc = SLEEP(0.5, 1);
    END;

    rc4 = FEXIST("out");
    rc4txt = SYSMSG();

    PUT _N_ @12 (rc:) (=);
RUN;

/* ------------------------------------------------------------------ */
/* 13. OPTIONAL CLEANUP                                                */
/* ------------------------------------------------------------------ */

/*
   Comment out this section if you want the HTML and TSV files to remain
   visible in the SAS OnDemand folder after zipping.
*/

%LET path = &whereisit/&myfolder;

FILENAME _folder_ "%BQUOTE(&path.)";

DATA filenames(KEEP=memname);
    handle = DOPEN('_folder_');

    IF handle > 0 THEN DO;
        count = DNUM(handle);

        DO i = 1 TO count;
            memname = DREAD(handle, i);

            IF SCAN(memname, 2, '.') = 'png'
                OR SCAN(memname, 2, '.') = 'html'
                OR SCAN(memname, 2, '.') = 'tsv'
                OR SCAN(memname, 2, '.') = 'csv'
            THEN OUTPUT filenames;
        END;
    END;

    rc = DCLOSE(handle);
RUN;

FILENAME _folder_ CLEAR;

DATA _NULL_;
    SET filenames;
    fname = 'todelete';
    rc = FILENAME(fname, QUOTE(CATS("&path", '/', memname)));
    rc = FDELETE(fname);
    rc = FILENAME(fname);
RUN;

/* END OF PROGRAMME */